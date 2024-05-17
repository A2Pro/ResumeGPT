import os
from dotenv import load_dotenv
import stripe
from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from openai import OpenAI
import pymongo
import docx
from pypdf import PdfReader 
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY")

gptclient = OpenAI(
    api_key=os.getenv("OPENAI_KEY"),
)

client = pymongo.MongoClient(os.getenv("MONGODB_URI"))

stripe_keys = {
    "secret_key": os.getenv("SECRET_KEY"),
    "publishable_key": os.getenv("PUBLIC_KEY"),
    "endpoint_secret": os.getenv("ENDPOINT_KEY")
}
stripe.api_key = stripe_keys["secret_key"]

def get_collection():
    collection = client['User_Passes']['user/passes']
    return collection #collection

def get_entry(username):
    entry  = get_collection().find_one({"name": username})
    return entry #collection

def get_credits(username):
    return get_entry(username)["credits"] #int

def get_password(username):
    return get_entry(username)["password"] #int

def add_creds(username, amount):
    get_collection().update_one(
      { "name" : username },
      { "$set": { "credits" : get_credits(username)+amount} } #void
    )

def add_user(username, password):
    newUserPass = {"name":username, "password" : password ,"credits":1}
    get_collection().insert_one(newUserPass)

def ask_gpt(prompt):
    response = gptclient.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": "You are an expert recruiter who has worked at the biggest tech companies for the last 20 years. You understand what makes a great resume and how to make a resume stand out for both the automated systems that are screening resumes and the internal recruiters that are reviewing resumes to determine if there is a potential job match. You are now helping candidates get interviews for the jobs they want by helping them tailor their resume for the role they wish to apply for. You are successful when the resume leads to an interview for the candidate.  You must be truthful in the experience of the candidate and cannot add experience that was not already on the resume, This is very important and must not be disobeyed. Essentially, what you have to alter the resume, keeping the structure, to adhere to to the company description of the jobs. You must not fabricate any acheivements. Here's the resume: "+ prompt,
                }
            ],
            model="gpt-3.5-turbo",
    )
    return response.choices[0].message.content #str


@app.route("/")
def index():
    if("logged_in" not in session.keys() or session["logged_in"] == False ):
        return redirect(url_for("login"))
    return render_template("index.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        session["username"] = username
        password = request.form['password']
        if(get_entry(username)!= None and password == get_password(username)):
            session["logged_in"] = True
            return("Yipee!")
        elif(get_entry(username)!= None and password != get_password(username)):
            session["logged_in"] = False
            return("Invalid password")
        elif(get_entry(username)==None):
            add_user(username, password)
            session["logged_in"] = True
            session["username"] = username
            return("account made!")
        return render_template('login.html', message='Invalid username or password!')
    return render_template('login.html', message='')

@app.route("/config")
def get_publishable_key():
    stripe_config = {"publicKey": stripe_keys["publishable_key"]}
    return jsonify(stripe_config)


@app.route("/create-checkout-session")
def create_checkout_session():
    domain_url = "http://localhost:5000/"
    stripe.api_key = stripe_keys["secret_key"]
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': 400,
                        'product_data': {
                            'name': 'One Resume',
                            'description': 'Alter just one resume using AI!',
                            'images': ['https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR7WQvQsdrb56ZfiSTm2mSxrjodRQ-hJIfhkg&usqp=CAU'],
                        },
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=domain_url + "success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=domain_url + "cancelled",
        )
        return jsonify({"sessionId": checkout_session["id"]})
    except Exception as e:
        print(e)
        return jsonify(error=str(e)), 403



@app.route("/webhook", methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, stripe_keys["endpoint_secret"]
        )

    except ValueError as e:
        # Invalid payload
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return 'Invalid signature', 400

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session(session)

    return 'Success', 200


def handle_checkout_session(session):
    print("Payment was successful.")


@app.route("/success")
def success():
    add_creds(session["username"], 1)
    return render_template("index.html", credits = get_credits(session["username"]))


@app.route("/cancelled")
def cancelled():
    return render_template("cancelled.html")

@app.route("/resumeupload")
def resume_upload():
    if(get_credits(session["username"]) <  1):
        return "Too few credits! Minimum 100 required!"
    add_creds(session['username'], -1)
    return render_template("resumeuploader.html")

def readtxt(file):
    doc = docx.Document(file)
    fullText = []
    for para in doc.paragraphs:
        fullText.append(para.text)
    return '\n'.join(fullText)


@app.route("/process", methods=['POST'])
def process():
    if 'file' not in request.files:
        return "No file uploaded", 400

    file = request.files['file']
    if file.filename == '':
        return "No file selected", 400
    fulltext = ""
    reader = PdfReader(file) 
    for page in reader.pages:
        fulltext += page.extract_text()
    response = ask_gpt(fulltext)
    return response

@app.route("/credits")
def return_credits():
    return render_template("credits.html",credits = get_credits(session["username"]))


if __name__ == "__main__":
    app.run()
