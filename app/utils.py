from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain.memory import ConversationBufferMemory
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import csv
from io import StringIO, BytesIO
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize LangChain
llm = ChatGroq(api_key=os.getenv("GROQ_API_KEY"), model="llama-3.3-70b-versatile")
memory = ConversationBufferMemory()

# Define role-based prompt templates
doctor_researcher_prompt = PromptTemplate(
    input_variables=['disease', 'question', 'history'],
    template="You are a medical AI assistant providing detailed scientific information to a doctor or researcher. The patient has been diagnosed with {disease} based on an OCT scan. Conversation history: {history}. Answer the following question: {question}. Provide a comprehensive explanation including the pathophysiology, risk factors, clinical implications, treatment options, and any relevant research findings."
)

patient_prompt = PromptTemplate(
    input_variables=['disease', 'question', 'history'],
    template="You are a medical AI assistant helping a patient understand their condition in simple terms. The patient has been diagnosed with {disease} based on an OCT scan. Conversation history: {history}. Answer the following question: {question}. Provide a simple explanation including what the disease is, how it occurs, precautions to take, food to eat or avoid, and whether they should see a doctor. Use plain language and avoid technical jargon."
)

# Initialize chains for each role
doctor_researcher_chain = RunnableSequence(doctor_researcher_prompt | llm)
patient_chain = RunnableSequence(patient_prompt | llm)

def generate_explanation(disease, question, user_role):
    history = memory.load_memory_variables({})['history']
    try:
        # Select the appropriate chain based on user role
        if user_role in ['doctor', 'researcher']:
            chain = doctor_researcher_chain
        else:  # patient
            chain = patient_chain
        
        response = chain.invoke({"disease": disease, "question": question, "history": history})
        memory.chat_memory.add_user_message(f"Disease: {disease}. Question: {question}")
        memory.chat_memory.add_ai_message(response.content)
        return response.content
    except Exception as e:
        return f"Error generating explanation: {e}"

def generate_pdf_report(scan, pdf_path):
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.drawString(100, 750, "OCTVision AI - Scan Report")
    c.drawString(100, 730, f"User ID: {scan.user_id}")
    c.drawString(100, 710, f"Date: {scan.date}")
    c.drawString(100, 690, f"Prediction: {scan.prediction}")
    c.drawString(100, 670, f"Confidence: {scan.confidence:.2f}%")
    c.drawString(100, 650, "Explanation:")
    text = c.beginText(100, 630)
    for line in scan.explanation.split('\n')[:10]:
        text.textLine(line)
    c.drawText(text)
    c.save()

def generate_csv(scans):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Prediction', 'Confidence', 'Explanation'])
    for scan in scans:
        writer.writerow([scan.date, scan.prediction, scan.confidence, scan.explanation])
    output.seek(0)
    csv_content = output.getvalue().encode('utf-8')
    bytes_io = BytesIO(csv_content)
    bytes_io.seek(0)
    output.close()
    return bytes_io