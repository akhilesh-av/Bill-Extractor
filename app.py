import streamlit as st
from groq import Groq
import os
from PIL import Image
import io
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv
import base64
import tempfile
from pdf2image import convert_from_bytes

# Load environment variables
load_dotenv()

# Initialize Groq client with environment variables
try:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    MODEL_NAME = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
except Exception as e:
    st.error(f"Failed to initialize Groq client: {str(e)}")
    st.stop()

def convert_pdf_to_images(pdf_bytes):
    """Convert PDF bytes to list of PIL Images"""
    images = convert_from_bytes(pdf_bytes)
    return images

def process_image_file(uploaded_file):
    """Process uploaded image file (JPG/PNG)"""
    try:
        image = Image.open(uploaded_file)
        if image.mode == 'RGBA':
            image = image.convert('RGB')
            
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG')
        return img_byte_arr.getvalue()
    except Exception as e:
        st.error(f"Error processing image: {str(e)}")
        return None

def process_pdf_file(uploaded_file):
    """Process uploaded PDF file"""
    try:
        pdf_bytes = uploaded_file.read()
        images = convert_pdf_to_images(pdf_bytes)
        return images
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        return None

def extract_data_from_image(image_bytes):
    """Extract data from image using Groq API"""
    try:
        prompt = """
        Analyze this bill/receipt/form carefully and extract all the data in a structured JSON format. 
        Include all relevant fields such as:
        - Vendor/seller information (name, address, contact)
        - Customer information (if available)
        - Date of transaction
        - Item list with descriptions, quantities, prices
        - Subtotals, taxes, discounts
        - Total amount
        - Payment method
        - Any other relevant information
        
        If any field is not present, omit it from the JSON.
        Return ONLY the JSON structure, no additional text or explanations.
        """
        
        # Convert image bytes to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.3,
            max_completion_tokens=1024,
            top_p=1,
            stream=False,
            stop=None,
        )
        
        return completion.choices[0].message.content
    except Exception as e:
        st.error(f"Error extracting data: {str(e)}")
        return None

def display_extracted_data(data):
    """Display extracted data in a user-friendly format"""
    try:
        st.subheader("Extracted Data")
        
        if data.strip().startswith('{') or data.strip().startswith('['):
            st.json(data)
        else:
            st.text_area("Extracted Information", value=data, height=300)
            
    except Exception as e:
        st.error(f"Error displaying data: {str(e)}")

def main():
    st.set_page_config(page_title="Document Data Extractor", page_icon=":receipt:")
    
    st.title("📄 Document Data Extractor")
    st.markdown("Upload a bill, receipt, or form (image or PDF) to extract structured data using Groq's AI.")
    
    if not os.getenv("GROQ_API_KEY"):
        st.error("GROQ_API_KEY is not set in the .env file. Please configure it to use this application.")
        return
    
    # Input method selection
    input_method = st.radio(
        "Select input method:",
        ("Upload a file (image/PDF)", "Enter image URL"),
        horizontal=True
    )
    
    if input_method == "Upload a file (image/PDF)":
        uploaded_file = st.file_uploader(
            "Choose a document...", 
            type=["jpg", "jpeg", "png", "pdf"],
            accept_multiple_files=False
        )
        
        if uploaded_file is not None:
            if uploaded_file.type.startswith('image/'):
                # Process image file
                image_bytes = process_image_file(uploaded_file)
                if image_bytes:
                    st.image(Image.open(io.BytesIO(image_bytes)), caption="Uploaded Image", use_container_width=True)
                    
                    if st.button("Extract Data"):
                        with st.spinner("Extracting data..."):
                            extracted_data = extract_data_from_image(image_bytes)
                            if extracted_data:
                                display_extracted_data(extracted_data)
                                st.download_button(
                                    label="Download Extracted Data",
                                    data=extracted_data,
                                    file_name="extracted_data.json",
                                    mime="application/json"
                                )
            
            elif uploaded_file.type == 'application/pdf':
                # Process PDF file
                images = process_pdf_file(uploaded_file)
                if images:
                    st.write(f"PDF contains {len(images)} pages")
                    
                    # Let user select which page to process
                    page_num = st.selectbox("Select page to analyze", range(len(images)), format_func=lambda x: f"Page {x+1}")
                    
                    # Display selected page
                    st.image(images[page_num], caption=f"Page {page_num+1}", use_container_width=True)
                    
                    if st.button("Extract Data from Selected Page"):
                        with st.spinner("Extracting data..."):
                            # Convert PIL image to bytes
                            img_byte_arr = io.BytesIO()
                            images[page_num].save(img_byte_arr, format='JPEG')
                            extracted_data = extract_data_from_image(img_byte_arr.getvalue())
                            
                            if extracted_data:
                                display_extracted_data(extracted_data)
                                st.download_button(
                                    label="Download Extracted Data",
                                    data=extracted_data,
                                    file_name="extracted_data.json",
                                    mime="application/json"
                                )
    
    else:  # Image URL method
        image_url = st.text_input("Enter the image URL:")
        
        if image_url:
            try:
                result = urlparse(image_url)
                if all([result.scheme, result.netloc]):
                    st.image(image_url, caption="Image from URL", use_container_width=True)
                    
                    if st.button("Extract Data"):
                        with st.spinner("Extracting data..."):
                            response = requests.get(image_url)
                            if response.status_code == 200:
                                extracted_data = extract_data_from_image(response.content)
                                if extracted_data:
                                    display_extracted_data(extracted_data)
                                    st.download_button(
                                        label="Download Extracted Data",
                                        data=extracted_data,
                                        file_name="extracted_data.json",
                                        mime="application/json"
                                    )
                            else:
                                st.error("Failed to download image from URL")
                else:
                    st.warning("Please enter a valid URL")
            except Exception as e:
                st.warning(f"Could not load image from this URL: {str(e)}")

if __name__ == "__main__":
    main()