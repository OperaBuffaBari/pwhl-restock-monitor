"""Email an alert when a size of a Shopify product comes back in stock."""

import json
import os
import smtplib
import sys
import time
import urllib.error
import urllib.request
from email.message import EmailMessage

PRODUCT_URL = os.environ.get(
    "PRODUCT_URL",
    "https://shop.thepwhl.com/products/adult-hilary-knight-21-pwhl-detroit-bauer-replica-home-jersey",
)
# Shopify titles XXL as "2XL"; accept either spelling.
SIZE_ALIASES = {s.strip().upper() for s in os.environ.get("SIZES", "2XL,XXL").split(",")}


def fetch_product(url, attempts=5):
    """Fetch the product's public Shopify JSON, backing off on rate limits."""
    request = urllib.request.Request(f"{url}.js", headers={"User-Agent": "Mozilla/5.0 restock-monitor"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == attempts:
                raise
            time.sleep(15 * attempt)


def find_variant(product):
    for variant in product["variants"]:
        if variant["title"].strip().upper() in SIZE_ALIASES:
            return variant
    sizes = [variant["title"] for variant in product["variants"]]
    sys.exit(f"No variant matching {sorted(SIZE_ALIASES)} on '{product['title']}'. Sizes listed: {sizes}")


def send_email(subject, body):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = os.environ["GMAIL_ADDRESS"]
    message["To"] = os.environ.get("ALERT_TO") or os.environ["GMAIL_ADDRESS"]
    message.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(os.environ["GMAIL_ADDRESS"], os.environ["GMAIL_APP_PASSWORD"])
        smtp.send_message(message)


def main():
    product = fetch_product(PRODUCT_URL)
    variant = find_variant(product)
    print(f"{product['title']} | {variant['title']} | available={variant['available']}")

    if "--test-email" in sys.argv:
        send_email("Restock monitor test", f"Test alert. Currently watching:\n{PRODUCT_URL}")
        print("Test email sent.")
        return

    if variant["available"]:
        link = f"{PRODUCT_URL}?variant={variant['id']}"
        send_email(
            f"IN STOCK: {product['title']} ({variant['title']})",
            f"{variant['title']} is back in stock. Buy it now:\n{link}",
        )
        print("Alert sent.")
        # Signals the workflow to disable itself so the alert isn't repeated every run.
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as output:
                output.write("in_stock=true\n")


if __name__ == "__main__":
    main()
