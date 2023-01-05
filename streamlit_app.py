from datetime import date
import streamlit as st
import pandas as pd
import numpy as np
from SPARQLWrapper import SPARQLWrapper, JSON
import plotly.express as px
import plotly.graph_objects as go

property_types = [
  'detached',
  'semi-detached',
  'terraced',
  'flat-maisonette'
]

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
  # add saon column if it doesn't exist
  if not 'saon' in df.columns:
    df['saon'] = np.nan
  # convert numerics
  df['amount'] = df['amount'].apply(pd.to_numeric, errors='coerce')
  df['paon'] = df['paon'].apply(pd.to_numeric, errors='ignore')
  # convert date
  df['date'] = pd.to_datetime(df['date'])
  # convert types
  df['propertyType'] = df['propertyType'].apply(lambda x: x.split('/')[-1])
  df['estateType'] = df['estateType'].apply(lambda x: x.split('/')[-1])
  # add a nice address column
  flat_addr = np.where(df['saon'].isna(), '', df['saon'].map(str) + ' ')
  df['address'] = flat_addr + df['paon'].map(str) + ' ' + df['street']
  df['address'] = df['address'].str.title()
  # reorder for better display
  df = df[['address', 'amount', 'date', 'postcode', 'propertyType', 'estateType',
          'saon', 'paon', 'street', 'town', 'county']]
  # sort by date
  df = df.sort_values(['street', 'paon', 'date'])
  return df


def get_multi_postcode_df(postcodes):
  dataframes = [get_postcode_df(code) for code in postcodes]
  return pd.concat(dataframes)


def plot_from_df(df, title):

  fig = px.scatter(
    df,
    x="date",
    y="amount",
    color="propertyType",
    hover_name="address", 
    hover_data=["postcode"],
    trendline="lowess",
    trendline_options=dict(frac=0.25),
    title=title,
    )
  fig.update_traces(marker=dict(size=10))

  return fig

# Now Streamlit
st.markdown(
  """
  Enter postcodes separated by commas. The space in the postcode is important!

  Optionally enter a potential sale price to have it shown on the plot.
  Optionally enter an address to highlight sales on the plot. Check the raw data 
  below to get the right address format.

  The plot is zoomable, and if you hover on a point you get the address.
  """
)
postcode_str = st.sidebar.text_input('Postcodes:')
st.sidebar.markdown("""---""")

purchase_price = st.sidebar.number_input('Suggested Price:', format='%d', step=5000)
purchase_addr = st.sidebar.text_input('Highlight Address:')
st.sidebar.write("Filters:")
type_checkboxes = [st.sidebar.checkbox(t, value=True) for t in property_types]

if st.button('Get Data'):
  with st.spinner('Wait for it...'):
    postcodes = [p.strip().upper() for p in postcode_str.split(',')]
    df = get_multi_postcode_df(postcodes)

    # filter according to property type
    types = np.array(property_types)[type_checkboxes]
    df_plot = df[df['propertyType'].isin(types)]

    fig = plot_from_df(df_plot, ', '.join(postcodes))

    if purchase_price:
      # A marker for the price itself
      fig.add_trace(
          go.Scatter(x=[date.today()],
                      y=[purchase_price],
                      mode='markers',
                      marker_color='yellow',
                      marker_size=15,
                      name='Suggested Price')
      )

    if purchase_addr:
      # and highlight the chosen property
      df_highlight = df_plot.query('address == @purchase_addr')
      fig.add_trace(
          go.Scatter(x=df_highlight['date'],
                      y=df_highlight['amount'],
                      mode='markers',
                      marker_symbol='circle-open',
                      marker_color='yellow',
                      marker_size=15,
                      name='Highlight Address')
      )

    st.plotly_chart(fig)
    my_expander = st.expander("Data", expanded=False)
    with my_expander:
        st.dataframe(df)
else:
    st.write('No Data')

