# Install with pip install firecrawl-py
from firecrawl import FirecrawlApp

app = FirecrawlApp(api_key='fc-61d509944b194cceb9e3e0bc0ee9e49e')

response = app.scrape_url(url='https://documenter.getpostman.com/view/27359911/2sB2cUBNkd#2c6dfb59-9652-461f-9549-1d6a1ced6874', params={
	'formats': [ 'markdown' ],
})

print(response['markdown'])