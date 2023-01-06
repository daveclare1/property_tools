from datetime import date
import streamlit as st
import pandas as pd
import numpy as np
from SPARQLWrapper import SPARQLWrapper, JSON
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(layout="wide")

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
  df = pd.DataFrame(res).applymap(lambda x: x['value'] if isinstance(x, dict) else np.NAN)
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
  Data comes from [landregistry.data.gov.uk](https://landregistry.data.gov.uk)

  Optionally enter a potential sale price to have it shown on the plot.
  Optionally enter an address to highlight sales on the plot. Check the raw data 
  below to get the right address format.

  The plot is zoomable, and if you hover on a point you get the address.
  """
)

query_params = st.experimental_get_query_params()
default_postcode = ', '.join(query_params.get('postcode', [''])).replace('-', ' ')
default_price = int(query_params.get('price', [0])[0])
default_addr = query_params.get('address', [''])[0].replace('-', ' ')
autorun = query_params.get('autorun', [False])[0]
filter_str = query_params.get('filter', ['1111'])[0]
if len(filter_str) != 4:
  filter_str = '1111'
default_filter = [True if c=='1' else False for c in list(filter_str)]

# SIDEBAR INPUTS
postcode_str = st.sidebar.text_input('Postcodes:', 
                                      value=default_postcode)
st.sidebar.markdown("""---""")
purchase_price = st.sidebar.number_input('Suggested Price:', format='%d',
                                          step=5000, value=default_price)
purchase_addr = st.sidebar.text_input('Highlight Address:',
                                        value=default_addr)
st.sidebar.write("Filters:")
type_checkboxes = [st.sidebar.checkbox(t, value=default_filter[i]) for i, t in enumerate(property_types)]

# MAIN AREA
if st.button('Get Data') or autorun:
  if len(postcode_str):
    with st.spinner('Wait for it...'):
      postcodes = [p.strip().upper() for p in postcode_str.split(',')]
      df = get_multi_postcode_df(postcodes)

      # filter according to property type
      types = np.array(property_types)[type_checkboxes]
      df_plot = df[df['propertyType'].isin(types)]

      fig = plot_from_df(df_plot, ', '.join(postcodes))
      fig.update_xaxes(showgrid=True)

      if purchase_price:
        # A marker for the price itself
        fig.add_trace(
            go.Scatter(x=[date.today()],
                        y=[purchase_price],
                        mode='markers',
                        # marker_color='yellow',
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
                        # marker_color='yellow',
                        marker_size=15,
                        marker_line_width=3,
                        name='Highlight Address')
        )

      st.plotly_chart(fig, theme="streamlit", use_conatiner_width=True)

      st.markdown(
        """[Rightmove listings](https://www.rightmove.co.uk/house-prices/SUB_POSTCODE.html?page=1) 
        (first postcode only)""".replace('SUB_POSTCODE', postcodes[0].lower().replace(' ', '-')))

      my_expander = st.expander("Data", expanded=False)
      with my_expander:
          st.dataframe(df)

  else:  # if 'get data' button pressed before postcode entered
    st.warning("""Enter a postcode first! If you're on a small screen, 
      the input panel on the left may be collapsed""", icon="⚠️")

else:  # before 'get data' button pressed
    st.write('Plot and data will show up here...')

with st.expander('Advanced'):
    st.markdown("""
    The URL for this page accepts queries to set inputs:
    - postcode=<str> sets the postcode field, can be duplicated. Use '-' instead of space
    - price=<int> sets the suggested price field
    - address=<str> sets the highglight address field, use '-' instead of space
    - filter=<4 bits> interpreted as 4 bits for the 4 property types, 1111 is all on
    - autorun=True fetches the data as you load the page or change an input
    Example: [URL]/?price=270000&postcode=S6-5DP&postcode=S6-5DR&filter=0110&autorun=True
    """)
