print("Starting the app...")
import requests
from bs4 import BeautifulSoup
import os
from elasticsearch import Elasticsearch
import gradio as gr
from urllib.parse import urljoin
import re

# Elasticsearch Configuration
es = Elasticsearch([{"host": "localhost", "port": 9200, "scheme":"http"}])

# Step 1: Scrape Wikipedia Page
URL = "https://en.wikipedia.org/wiki/Machine_learning"
response = requests.get(URL)
soup = BeautifulSoup(response.content, "html.parser")

# Extract Text Content
def scrape_text(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # **Step 1: Remove all citation references enclosed in <sup> tags**
    for sup_tag in soup.find_all('sup'):
        sup_tag.decompose()  # Removes the <sup> tag and its content

    # **Step 2: Extract text content**
    paragraphs = soup.find_all('p')
    text_content = " ".join([para.get_text() for para in paragraphs])

    # **Step 3: Use regex to remove any remaining numbers inside square brackets**
    cleaned_text = re.sub(r'\[\d+\]', '', text_content)  # Removes [41], [42], etc.

    # **Step 4: Remove extra spaces caused by deletions**
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    return cleaned_text

# Extract Images
def scrape_images(url):
    base_url = "https://en.wikipedia.org/wiki/Machine_learning"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    img_tags = soup.find_all('img') # Find all image tags
    
    os.makedirs('images', exist_ok=True) # Create an images folder
    image_paths = [] # To store paths of saved images
    
    for i, img in enumerate(img_tags):
        img_url = urljoin(base_url, img['src'])  # Handle relative paths
        file_path = f'images/img_{i}.jpg'
        image_paths.append(file_path)
        with open(file_path, 'wb') as img_file:
            img_file.write(requests.get(img_url).content)
    return image_paths

# Step 2: Store Data in Elasticsearch
def index_data():
    url = "https://en.wikipedia.org/wiki/Machine_learning"
    text_data = scrape_text("https://en.wikipedia.org/wiki/Machine_learning")
    image_data = scrape_images(url)
  
    # Index text data in Elasticsearch
    es.index(index="text", body={"content": text_data})

    # Index Text
    for i, item in enumerate(text_data.split("\n")):
        if item.strip():
            # Clean the text again before indexing (to ensure no citation numbers remain)
            cleaned_item = re.sub(r'\[\d+\]', '', item.strip())
            es.index(index="wiki_text", id=i, document={"content": cleaned_item})

    # Index Images paths in Elasticsearch
    for i, img_path in enumerate(image_data):
        es.index(index="wiki_images", id=i, document={"path":img_path})

# Step 3: Search Engine with Gradio
def search(query):
    results = []
    # Search Text
    text_hits = es.search(index="wiki_text", query={"match": {"content": query}})
    for hit in text_hits["hits"]["hits"]:
        # Clean the search results to remove any remaining citation numbers
        cleaned_result = re.sub(r'\[\d+\]', '', hit["_source"]["content"])
        results.append(cleaned_result)

    # Search Images
    img_hits = es.search(index="wiki_images", query={"match": {"path": query}})
    for hit in img_hits["hits"]["hits"]:
        # Append the image path to the results
        results.append(hit["_source"]["path"])

    return results

# Gradio Interface
def search_engine(query):
    results = search(query)
    
    # Separate text and image results
    text_results = [result for result in results if not result.endswith(('.jpg', '.png', '.jpeg'))]
    image_results = [result for result in results if result.endswith(('.jpg', '.png', '.jpeg'))]
    
    # Display text results
    text_output = "\n".join(text_results)
    
    # Display image results
    image_output = []
    for img_path in image_results:
        image_output.append(img_path)
    
    return text_output, image_output

# Customizing the gradio UI
with gr.Blocks(theme="soft") as demo:
    # Title and Description
    gr.Markdown(
        """
        # Wikipedia Search Engine
        **Search for text and images from Wikipedia's Machine Learning page.**
        """
    )
    
    # Search Input and Button
    with gr.Row():
        query_input = gr.Textbox(label="Enter your search query", placeholder="Type here...", elem_id="search-box")
        submit_button = gr.Button("🔍 Search", elem_id="search-btn")
    
    # Results Section
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Text Results")
            text_output = gr.Textbox(label="Text Results", interactive=False)
        with gr.Column():
            gr.Markdown("### Image Results")
            image_output = gr.Gallery(label="Image Results")
    
    # Footer
    gr.Markdown(
        """
        ---
        *Built with ❤️ using Gradio and Elasticsearch.*
        """
    )
    
    # Link the button to the search function
    submit_button.click(search_engine, inputs=query_input, outputs=[text_output, image_output])

# Index the data first
index_data()

# Run Gradio App
demo.launch()