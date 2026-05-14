# AI-Accelerated Compliance Pipeline

## Project Overview:
### An AI-powered, fully local pipeline that analyzes PDF documents against customizable compliance rules. Built with Streamlit, LangGraph, and Ollama, this tool extracts text from PDFs and uses a local Large Language Model (LLM) to generate detailed compliance reports without needing paid API keys or an internet connection.

## Features:

### Fully Local AI: Uses Ollama and the Llama 3 model for 100% private, free, and local inference.
### Dynamic Rules Engine: Update compliance rules directly from the UI to test different legal standards instantly.
### Intelligent Orchestration: Powered by LangGraph to manage the AI workflow.
### Interactive UI: Built with Streamlit for seamless PDF uploads, processing, and report generation.

## Prerequisites & Setup:

### Install Ollama (Local LLM Engine): 
#### Because this project runs locally, you need to install Ollama and download the LLM before running the application.

#### 1.Download Ollama: Go to ollama.com and download the installer for your operating system (Windows, Mac, or Linux).
#### 2. Install: Run the installer.
#### 3. Download the Llama 3 Model: Open your terminal or command prompt and run the following command: ollama run llama3
#### Note: Once it finishes downloading and gives you a chat prompt, you can type `/bye` to exit. Ollama will now run quietly in the background.

### Set Up the Python Environment

#### Ensure you have Python 3.8 or higher installed. It is highly recommended to use a virtual environment.
#### Clone or create the project folder and navigate into it.
#### Create a virtual environment.(python -m venv .venv)
#### Activate the virtual environment.(source .venv/bin/activate)
#### Install the dependencies.(pip install -r requirements.txt)


## Running the Application

### 1. Ensure Ollama is running: Make sure the Ollama application is open and running on your machine.
### 2. Start the Streamlit App: In your terminal (with the virtual environment activated), run: streamlit run app.py
### 3. Open your browser: Streamlit will automatically open a new tab in your default web browser(usually at http://localhost:8501).

## How to Use

### Configure Rules: Use the sidebar on the left to review or edit the compliance rules. You can type any specific legal requirements you want the AI to check for.
### Upload a PDF: Click the upload box in the main window to select a PDF document from your computer.
### Run Check: Click the "Run Compliance Check" button. The app will extract the text, pass it to LangGraph, and analyze it using Ollama.
### Review & Download: Read the generated compliance report on the screen. You can download the final report as a .txt file using the download button at the bottom.


## Project Structure
 
### app.py # Streamlit user interface and application logic
### workflow.py # LangGraph orchestration and Ollama LLM setup
### pdf_processor.py # PyMuPDF logic for extracting text from documents
### requirements.txt # Python package dependencies