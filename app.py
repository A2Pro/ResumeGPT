import os
from dotenv import load_dotenv
import stripe
from flask import Flask, jsonify, render_template, request
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

client = OpenAI(
    api_key=os.getenv("OPENAI_KEY"),
)

stripe_keys = {
    "secret_key": os.getenv("SECRET_KEY"),
    "publishable_key": os.getenv("PUBLIC_KEY"),
    "endpoint_secret": os.getenv("ENDPOINT_KEY")
}
stripe.api_key = stripe_keys["secret_key"]


def ask_gpt(prompt):
    response = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": "You are an expert recruiter who has worked at the biggest tech companies for the last 20 years. You understand what makes a great resume and how to make a resume stand out for both the automated systems that are screening resumes and the internal recruiters that are reviewing resumes to determine if there is a potential job match. You are now helping candidates get interviews for the jobs they want by helping them tailor their resume for the role they wish to apply for. You are successful when the resume leads to an interview for the candidate.  You must be truthful in the experience of the candidate and cannot add experience that was not already on the resume, This is very important and must not be disobeyed. Here's the resume: "+ prompt,
                }
            ],
            model="gpt-3.5-turbo",
        )
    return response.choices[0].message.content


@app.route("/")
def index():
    return render_template("index.html")


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
            line_items=[{
                         'price_data': {
                             'currency': 'usd',
                             'unit_amount': 4000,
                             'product_data': {
                                 'name': 'One Resume',
                                 'description': 'Alter just one resume using AI!',
                                 'images': ['https://example.com/t-shirt.png'],
                              },
                         },
                        'quantity': 1,
                     }],
            mode='payment',
            success_url=domain_url + "success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=domain_url + "cancelled",
        )
        return jsonify({"sessionId": checkout_session["id"]})
    except Exception as e:
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
    return render_template("success.html")


@app.route("/cancelled")
def cancelled():
    return render_template("cancelled.html")


if __name__ == "__main__":
    app.run()
