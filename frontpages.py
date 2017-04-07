
# coding: utf-8

# http://www.newseum.org/todaysfrontpages/?tfp_display=list

# In[ ]:

import os, time, datetime, random, logging as lg
import requests, bs4
import config
from abbrev_state import abbrev_state
from twitter_keys import consumer_key, consumer_secret, access_token_key, access_token_secret


# ## Define functions

# In[ ]:

def log(message, level=lg.INFO, name='fp', filename='fp'):

    # get the current logger (or create a new one, if none), then log message at requested level
    logger = get_logger(level=level, name=name, filename=filename)
    if level == lg.DEBUG:
        logger.debug(message)
    elif level == lg.INFO:
        logger.info(message)
    elif level == lg.WARNING:
        logger.warning(message)
    elif level == lg.ERROR:
        logger.error(message)


# In[ ]:

def get_logger(level, name, filename, folder=config.log_folder):
    
    logger = lg.getLogger(name)
    
    # if a logger with this name is not already set up
    if not getattr(logger, 'handler_set', None):
        
        # get today's date and construct a log filename
        todays_date = datetime.datetime.today().strftime('%Y_%m_%d')
        log_filename = '{}/{}_{}.log'.format(folder, filename, todays_date)
        
        # if the logs folder does not already exist, create it
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        # create file handler and log formatter and set them up
        handler = lg.FileHandler(log_filename, encoding='utf-8')
        formatter = lg.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.handler_set = True
    
    return logger


# In[ ]:

def get_papers_sample(papers, n, usa_proportion):
    
    usa_papers = [paper for paper in papers if 'USA' in paper['place']]
    world_papers = [paper for paper in papers if 'USA' not in paper['place']]
    log('we have {} papers: {} from USA and {} from elsewhere'.format(len(papers), 
                                                                      len(usa_papers), 
                                                                      len(world_papers)))
    
    random.shuffle(usa_papers)
    usa_papers_sample = usa_papers[:int(n*usa_proportion)]
    
    random.shuffle(world_papers)
    world_papers_sample = world_papers[:int(n*(1-usa_proportion))]
    
    papers_sample = usa_papers_sample + world_papers_sample
    random.shuffle(papers_sample)
    
    log('sampled {} papers: {} from USA and {} from elsewhere'.format(len(papers_sample), 
                                                                      len(usa_papers_sample), 
                                                                      len(world_papers_sample)))
    return papers_sample


# In[ ]:

# function to download an image from url to save folder
def download_image(paper_id, img_filepath, url):
    start_time = time.time()
    img_data = requests.get(url).content
    with open(img_filepath, mode) as handler:
        handler.write(img_data)
    log('downloaded {} and saved as "{}" in {:,.2f} seconds'.format(url, img_filepath, time.time()-start_time))


# In[ ]:

def get_paper_links_date(paper_id, url_template='http://www.newseum.org/todaysfrontpages/?tfp_id={}'):
    
    start_time = time.time()
    url = url_template.format(paper_id)
    response = requests.get(url)
    content = response.content.decode('utf-8')
    soup = bs4.BeautifulSoup(content, 'html5lib')
    
    # get the link to the newspaper's homepage
    item = soup.find('span', {'class':'fa fa-external-link'}).find_parent('a')
    paper_link = item['href']
    
    # get the link to the image
    item = soup.find('p', {'class':'tfp-thumbnail'}).a
    img_link = item['href']
    
    # get the current local date
    item = soup.find('div', {'class':'tfp-pane-detail'}).h4
    local_date = item.text
    
    log('retrieved/parsed local date, newspaper link, and image url in {:,.2f} seconds'.format(time.time()-start_time))
    return paper_link, img_link, local_date


# In[ ]:

def geocode(query):
    
    # send the query to the nominatim geocoder and parse the json response
    start_time = time.time()
    url_template = 'https://nominatim.openstreetmap.org/search?format=json&limit=1&q={}'
    url = url_template.format(query)
    response = requests.get(url, timeout=60)
    results = response.json()
    
    # if results were returned, parse lat and long out of the result
    if len(results) > 0 and 'lat' in results[0] and 'lon' in results[0]:
        lat = float(results[0]['lat'])
        lng = float(results[0]['lon'])
        log('geocoded "{}" to {} in {:,.2f} seconds'.format(query, (lat, lng), time.time()-start_time))
        return lat, lng
    else:
        log('geocoder returned no results for query "{}"'.format(query), level=lg.WARN)
        return None, None


# In[ ]:

def make_status(name, place, paper_link, local_date=None):
    if local_date is None:
        status = 'Today\'s front page from:\n{}\n{}\n{}'.format(name, place, paper_link)
    else:
        status = '{}\n{}\n{}\n{}'.format(name, place, local_date, paper_link)
    return status


# ## Get list of all newspapers

# In[ ]:

log('script started')
config_str = ', '.join(['{}={}'.format(item, getattr(config, item)) for item in dir(config) if not item.startswith('_')])
log('config: {}'.format(config_str))


# In[ ]:

# get the web page with the list of all newspapers
start_time = time.time()
homepage_url = 'http://www.newseum.org/todaysfrontpages/?tfp_display=list'
response = requests.get(homepage_url)

# parse the html and extract the list of newspapers items
content = response.content.decode('utf-8')
soup = bs4.BeautifulSoup(content, 'html5lib')
items = soup.find_all('div', {'class':'tfp-list-item'})
log('retrieved and parsed list of newspapers in {:,.2f} seconds'.format(time.time()-start_time))


# In[ ]:

# extract each newspaper's id, name, and place
papers = []
for item in items:
    paper = {}
    paper['id'] = item.a['name']
    paper['name'] = item.a.em.text
    paper['place'] = item.small.text
    papers.append(paper)
    
# try to clean up US state place strings by replacing weird abbrevs with name instead
for paper in papers:
    try:
        place = paper['place'].replace('  ', ' ').strip(' ')
        place = place.replace(' USA', ', USA')
        place_parts = place.split(', ')
        if len(place_parts) == 3 and place_parts[2] == 'USA':
            abbrev = paper['id'].split('_')[0]
            place_parts[1] = abbrev_state[abbrev]
        paper['place'] = ', '.join(place_parts)
    except:
        pass

log('extracted and cleaned newspaper details')


# In[ ]:

papers_sample = get_papers_sample(papers=papers, n=config.n, usa_proportion=config.usa_proportion)


# ## Prep image saving

# In[ ]:

# image file saving config
mode = 'wb'
file_ext = 'jpg'

# create image save folder name
if config.img_folder_date:
    yyyymmdd = datetime.datetime.today().strftime('%Y%m%d')
    save_folder = '{}/{}'.format(config.img_folder, yyyymmdd)
else:
    save_folder = config.img_folder

# if it doesn't already exist, create the image save folder
if not os.path.exists(save_folder):
    os.makedirs(save_folder)


# ## Tweet

# In[ ]:

# connect to the twitter api
import twitter
start_time = time.time()
api = twitter.Api(consumer_key=consumer_key,
                  consumer_secret=consumer_secret,
                  access_token_key=access_token_key,
                  access_token_secret=access_token_secret)
user = api.VerifyCredentials().AsDict()
log('logged into twitter as "{}" id={} in {:,.2f} seconds'.format(user['screen_name'], user['id'], time.time()-start_time))


# In[ ]:

# tweet each paper
for paper in papers_sample:
    try:
        # get link to paper, download image, geocode place, then make status
        log('processing "{}"'.format(paper['id']))
        img_filepath = '{}/{}.{}'.format(save_folder, paper['id'], file_ext)
        paper_link, img_link, local_date = get_paper_links_date(paper['id'])
        download_image(paper['id'], img_filepath, url=img_link)
        lat, lng = geocode(paper['place'])
        status = make_status(paper['name'], paper['place'], paper_link, local_date=local_date)
        
        start_time = time.time()
        if lat is None or lng is None:
            # tweet just the status + image
            result = api.PostUpdate(status=status, media=img_filepath)
        else:
            # otherwise we have lat/lng, so tweet the status + image + location coordinates
            result = api.PostUpdate(status=status, media=img_filepath, latitude=lat, longitude=lng, display_coordinates=True)
        log('tweeted "{}" with media "{}" in {:,.2f} seconds'.format(repr(status), img_filepath, time.time()-start_time))
        time.sleep(config.pause_duration)
    except Exception as e:
        log(e, level=lg.ERROR)
        time.sleep(config.pause_error)

