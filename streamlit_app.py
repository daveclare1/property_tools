import streamlit as st
import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON
import plotly.express as px

def get_postcode_df(postcode:str):
  # https://landregistry.data.gov.uk/app/qonsole
  # https://linkedwiki.com/query/UK_Goverment_Land_Registry_Dataset_Exploration?lang=EN

  sparql = SPARQLWrapper("http://landregistry.data.gov.uk/landregistry/query")
  sparql.setQuery(
    """
    prefix xsd: <http://www.w3.org/2001/XMLSchema#>
    prefix lrppi: <http://landregistry.data.gov.uk/def/ppi/>
    prefix lrcommon: <http://landregistry.data.gov.uk/def/common/>

    SELECT ?paon ?saon ?street ?town ?county ?postcode ?amount ?date ?propertyType ?estateType
WHERE
{
  VALUES ?postcode {"SUB_POSTCODE"^^xsd:string}

  ?addr lrcommon:postcode ?postcode.

  ?transx lrppi:propertyAddress ?addr ;
          lrppi:pricePaid ?amount ;
          lrppi:transactionDate ?date ;
          lrppi:propertyType ?propertyType;
          lrppi:estateType ?estateType.

  OPTIONAL {?addr lrcommon:county ?county}
  OPTIONAL {?addr lrcommon:paon ?paon}
  OPTIONAL {?addr lrcommon:saon ?saon}
  OPTIONAL {?addr lrcommon:street ?street}
  OPTIONAL {?addr lrcommon:town ?town}
}
        """.replace('SUB_POSTCODE', postcode)
    )
  sparql.setReturnFormat(JSON)
  results = sparql.query().convert()
  res = results['results']['bindings']
  df = pd.DataFrame(res).applymap(lambda x: x['value'])
  # convert numerics
  cols = ['paon', 'amount']
  df[cols] = df[cols].apply(pd.to_numeric, errors='ignore', axis=1)
  # convert date
  df['date'] = pd.to_datetime(df['date'])
  # convert types
  df['propertyType'] = df['propertyType'].apply(lambda x: x.split('/')[-1])
  df['estateType'] = df['estateType'].apply(lambda x: x.split('/')[-1])
  # add a nice address column
  df['address'] = df['paon'].map(str) + ' ' + df['street'].str.title()
  # sort by date
  df = df.sort_values(['street', 'paon', 'date'])
  return df


def get_multi_postcode_df(postcodes):
  dataframes = [get_postcode_df(code) for code in postcodes]
  return pd.concat(dataframes)


def plot_from_df(df):

  fig = px.scatter(
    df,
    x="date",
    y="amount",
    color="propertyType",
    hover_name="address", 
    hover_data=["postcode"],
    trendline="lowess",
    trendline_options=dict(frac=0.25),
    title=postcode_str,
    )
  fig.update_traces(marker=dict(size=10))

  addresses = df.groupby('address')

  for name, addr in addresses:
    fig.add_traces(
        list(px.line(
            addr,
            x="date",
            y="amount",
        ).update_traces(opacity=0.15).select_traces())
    )
  return fig

# Now Streamlit
postcode_str = st.text_input('Postcodes:')

if st.button('Get Data'):
  with st.spinner('Wait for it...'):
    df = get_multi_postcode_df(postcode_str.split(', '))
    fig = plot_from_df(df)
    st.plotly_chart(fig)
else:
    st.write('No Data')
