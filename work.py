import requests
import json
import uuid
import os
import time
import threading
from dotenv import load_dotenv
import websocket

load_dotenv()

def create_new_presentation(auth_token):
    url = "https://alai-standalone-backend.getalai.com/create-new-presentation"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }
    payload = {
        "presentation_id": str(uuid.uuid4()),
        "presentation_title": "AI Generated Presentation",
        "create_first_slide": True,
        "default_color_set_id": 0,
        "theme_id": "a6bff6e5-3afc-4336-830b-fbc710081012"
    }
    try:
        print(f"Creating new presentation with payload: {json.dumps(payload, indent=2)}")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        presentation_data = response.json()
        print(f"Successfully created presentation! Response: {json.dumps(presentation_data, indent=2)}")
        return presentation_data
    except requests.exceptions.RequestException as e:
        print(f"Error creating presentation: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Response: {e.response.text}")
        return None

def create_new_slide(auth_token, presentation_id, slide_order):
    url = "https://alai-standalone-backend.getalai.com/create-new-slide"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }
    new_slide_id = str(uuid.uuid4())
    payload = {
        "slide_id": new_slide_id,
        "presentation_id": presentation_id,
        "product_type": "PRESENTATION_CREATOR",
        "slide_order": slide_order,
        "color_set_id": 0
    }
    try:
        print(f"Creating new slide with payload: {json.dumps(payload, indent=2)}")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        slide_data = response.json()
        print(f"Successfully created slide! Response: {json.dumps(slide_data, indent=2)}")
        return new_slide_id
    except requests.exceptions.RequestException as e:
        print(f"Error creating new slide: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Response: {e.response.text}")
        return None

def generate_slides_outline(auth_token, presentation_id, topic, instructions):
    ws_url = f"wss://alai-standalone-backend.getalai.com/ws/generate-slides-outline?token={auth_token}"
    outlines = []
    ws_messages = []
    connection_closed = threading.Event()
    ws_error = None

    def on_message(ws, message):
        nonlocal ws_messages, outlines
        print(f"Outline WebSocket message received: {message[:200]}...")
        ws_messages.append(message)
        try:
            data = json.loads(message)
            if isinstance(data, dict) and "heading" in data and "slide_context" in data:
                outlines.append(data)
            elif isinstance(data, dict) and "outlines" in data and isinstance(data["outlines"], list):
                outlines = data["outlines"]
            elif isinstance(data, list):
                outlines = data
            else:
                print(f"Received unexpected message format: {message[:100]}...")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON in outline WS: {e}")
        except Exception as e:
            print(f"Error processing outline message: {e}")

    def on_error(ws, error):
        nonlocal ws_error
        print(f"Outline WebSocket error: {error}")
        ws_error = error
        connection_closed.set()

    def on_close(ws, close_status_code, close_msg):
        print(f"Outline WebSocket connection closed. Status code: {close_status_code}, Message: {close_msg}")
        connection_closed.set()

    def on_open(ws):
        print("Outline WebSocket connection opened for generating outlines")
        request_data = {
            "auth_token": auth_token,
            "presentation_id": presentation_id,
            "presentation_instructions": instructions,
            "raw_context": topic,
            "slide_order": 0,
            "slide_range": "2-5"
        }
        print(f"Sending outline request: {json.dumps(request_data, indent=2)}")
        try:
            ws.send(json.dumps(request_data))
        except Exception as e:
            print(f"Error sending outline request: {e}")
            on_error(ws, e)

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()

    print("Waiting for outline WebSocket connection to close or timeout...")
    timeout = 45
    connection_closed.wait(timeout=timeout)

    if ws_error:
        print("Outline generation failed due to WebSocket error.")
    elif not outlines:
        print("Outline connection closed or timed out without receiving valid outlines.")

    if wst.is_alive():
        if ws.sock and ws.sock.connected:
            try:
                ws.close()
            except Exception as e:
                print(f"Error during final close: {e}")
        wst.join(timeout=2)
        if wst.is_alive():
            print("Warning: Outline WebSocket thread did not exit gracefully.")

    try:
        parsed_messages = [json.loads(msg) for msg in ws_messages]
        with open("outline_ws_messages.log", "w") as f:
            json.dump(parsed_messages, f, indent=2)
        print("Outline WebSocket messages saved to outline_ws_messages.log")
    except Exception as e:
        print(f"Error saving outline WS messages: {e}")

    print("\nDETAILED OUTLINES")
    for i, outline in enumerate(outlines):
        print(f"\nOUTLINE {i+1}:")
        print(f"Heading: {outline.get('heading', 'No heading')}")
        print(f"Context: {outline.get('slide_context', 'No context')}")
        print(f"Instructions: {outline.get('slide_instructions', 'No instructions')}")

    return outlines

def get_calibration_sample_text(auth_token, presentation_id, raw_context):
    url = "https://alai-standalone-backend.getalai.com/get-calibration-sample-text"
    headers = { 
        "Content-Type": "application/json", 
        "Accept": "application/json", 
        "Authorization": f"Bearer {auth_token}" 
    }
    payload = {
        "presentation_id": presentation_id,
        "raw_context": raw_context
    }
    try:
        print(f"Requesting calibration sample text with payload: {json.dumps(payload, indent=2)}")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        calibration_data = response.json()
        print(f"Successfully retrieved calibration data: {json.dumps(calibration_data, indent=2)}")
        return calibration_data
    except requests.exceptions.RequestException as e:
        print(f"Error getting calibration text: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Response: {e.response.text}")
        return None

def calibrate_verbosity(auth_token, presentation_id, original_text, verbosity_level, previous_verbosity_level=None, tone_type="PROFESSIONAL", tone_instructions=None):
    url = "https://alai-standalone-backend.getalai.com/calibrate-verbosity"
    headers = { "Content-Type": "application/json", "Accept": "application/json", "Authorization": f"Bearer {auth_token}" }
    payload = { 
        "original_text": original_text, 
        "presentation_id": presentation_id, 
        "verbosity_level": verbosity_level, 
        "tone_type": tone_type 
    }
    if previous_verbosity_level is not None:
        payload["previous_verbosity_level"] = previous_verbosity_level
    if tone_instructions is not None:
        payload["tone_instructions"] = tone_instructions
    try:
        print(f"Calibrating verbosity with payload: {json.dumps(payload, indent=2)}")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        print(f"Successfully calibrated verbosity! Response: {json.dumps(result, indent=2)}")
        return result
    except requests.exceptions.RequestException as e:
        print(f"Error calibrating verbosity: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Response: {e.response.text}")
        return None

def stream_slide_variants(auth_token, presentation_id, slide_id, outline, starting_slide_order):
    ws_url = f"wss://alai-standalone-backend.getalai.com/ws/create-and-stream-slide-variants?token={auth_token}"
    variants = []
    ws_messages = []
    connection_closed = threading.Event()
    ws_error = None

    def on_message(ws, message):
        nonlocal ws_messages, variants
        print(f"Slide Variant WebSocket message received: {message[:200]}...")
        ws_messages.append(message)
        try:
            data = json.loads(message)
            if isinstance(data, dict) and "variant_id" in data:
                variants.append(data)
            elif isinstance(data, dict) and "id" in data and "slide_id" in data:
                variant_info = {
                    "variant_id": data.get("id"),
                    "slide_id": data.get("slide_id"),
                    "slide_content": data.get("element_slide", {})
                }
                variants.append(variant_info)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "id" in item:
                        variant_info = {
                            "variant_id": item["id"],
                            "slide_id": item.get("slide_id", slide_id),
                            "slide_content": item.get("element_slide", {})
                        }
                        variants.append(variant_info)
            else:
                print(f"Received message in unexpected format: {message[:100]}...")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON in variants WS: {e}")
        except Exception as e:
            print(f"Error processing variants message: {e}")

    def on_error(ws, error):
        nonlocal ws_error
        print(f"Variants WebSocket error: {error}")
        ws_error = error
        connection_closed.set()

    def on_close(ws, close_status_code, close_msg):
        print(f"Variants WebSocket connection closed. Status code: {close_status_code}, Message: {close_msg}")
        connection_closed.set()

    def on_open(ws):
        print("Variants WebSocket connection opened for creating slide variants")
        request_data = {
            "auth_token": auth_token,
            "presentation_id": presentation_id,
            "slide_id": slide_id,
            "layout_type": "AI_GENERATED_LAYOUT",
            "images_on_slide": [],
            "slide_specific_context": outline.get("slide_context", "ww3"),
            "additional_instructions": "ww3",
            "update_tone_verbosity_calibration_status": False,
            "starting_slide_order": starting_slide_order,
            "presentation_instructions": outline.get("slide_instructions", "")
        }
        print(f"Sending variants request: {json.dumps(request_data, indent=2)}")
        try:
            ws.send(json.dumps(request_data))
        except Exception as e:
            print(f"Error sending variants request: {e}")
            on_error(ws, e)

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()

    print("Waiting for variants WebSocket connection to close or timeout...")
    timeout = 120
    connection_closed.wait(timeout=timeout)

    if ws_error:
        print("Variants generation failed due to WebSocket error.")
    elif not variants:
        print("Variants connection closed or timed out without receiving valid variants.")

    if wst.is_alive():
        if ws.sock and ws.sock.connected:
            try:
                ws.close()
            except Exception as e:
                print(f"Error during final close: {e}")
        wst.join(timeout=2)
        if wst.is_alive():
            print("Warning: Variants WebSocket thread did not exit gracefully.")

    try:
        with open("variants_ws_messages_raw.log", "w") as f:
            for msg in ws_messages:
                f.write(msg + "\n")
        parsed_messages = []
        for msg in ws_messages:
            try:
                parsed_messages.append(json.loads(msg))
            except json.JSONDecodeError:
                parsed_messages.append({"unparseable_message": msg[:100] + "..."})
        with open("variants_ws_messages.log", "w") as f:
            json.dump(parsed_messages, f, indent=2)
        print("Variants WebSocket messages saved to variants_ws_messages.log")
    except Exception as e:
        print(f"Error saving variants WS messages: {e}")

    print("\n===== SLIDE VARIANTS =====")
    for i, variant in enumerate(variants):
        print(f"\nVARIANT {i+1}:")
        print(f"Variant ID: {variant.get('variant_id', 'No ID')}")
        print(f"Slide ID: {variant.get('slide_id', 'No Slide ID')}")
        content_preview = str(variant.get('slide_content', {}))
        print(f"Content Preview: {content_preview[:100]}...")
    print("\n==========================")

    return variants

def set_active_variant(auth_token, slide_id, variant_id):
    url = "https://alai-standalone-backend.getalai.com/set-active-variant"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }
    payload = {
        "slide_id": slide_id,
        "variant_id": variant_id
    }
    try:
        print(f"Setting active variant with payload: {json.dumps(payload, indent=2)}")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        print(f"Successfully set active variant! Response: {json.dumps(result, indent=2)}")
        return result
    except requests.exceptions.RequestException as e:
        print(f"Error setting active variant: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Response: {e.response.text}")
        return None


from firecrawl import FirecrawlApp

def scrape_website_content(url):
    firecrawl_app = FirecrawlApp(api_key='fc-61d509944b194cceb9e3e0bc0ee9e49e')
    print(f"Scraping website: {url}")
    response = firecrawl_app.scrape_url(url=url, params={'formats': ['markdown']})
    if 'markdown' in response:
        content = response['markdown']
        print("Successfully scraped website content.")
        return content
    else:
        print("Markdown content not found in response; using empty context.")
        return ""


if __name__ == "__main__":
    auth_token = os.getenv("AUTH_TOKEN")
    if not auth_token:
        print("AUTH_TOKEN environment variable not found. Please create a .env file with AUTH_TOKEN='your_token'")
        exit(1)

    website_url = input("Enter the website URL to use as input context: ").strip()
    if not website_url:
        print("No website URL provided. Exiting.")
        exit(1)

    scraped_content = scrape_website_content(website_url)
    topic = scraped_content  # Replace with a shortened version if needed.
    instructions = "Generate detailed and descriptive slides based on the provided website content."

    print("Starting presentation generation process...")

    # 1. Create presentation
    print("\nSTEP 1: CREATE NEW PRESENTATION")
    presentation_data = create_new_presentation(auth_token)
    if not presentation_data or "id" not in presentation_data:
        exit(1)
    presentation_id = presentation_data.get("id")
    first_slide_id = None
    if presentation_data.get("slides") and isinstance(presentation_data["slides"], list) and len(presentation_data["slides"]) > 0:
        first_slide = presentation_data["slides"][0]
        if isinstance(first_slide, dict) and "id" in first_slide:
            first_slide_id = first_slide.get("id")
    print(f"Created presentation with ID: {presentation_id}")
    if first_slide_id:
        print(f"Detected first slide ID: {first_slide_id}")
    else:
        print("Warning: Could not detect ID of the initially created slide.")

    # 2. Generate outlines using the website content as context
    print(f"\n==== STEP 2: GENERATING OUTLINES FOR THE SCRAPED WEBSITE CONTENT ====")
    outlines = generate_slides_outline(auth_token, presentation_id, topic, instructions)
    if not outlines:
        print("Failed to generate outlines. Check outline_ws_messages.log. Exiting.")
        exit(1)
    print(f"\nGenerated {len(outlines)} outlines:")
    for i, outline in enumerate(outlines):
        print(f"- {outline.get('heading', f'Outline {i+1}')}")
    selected_outlines = outlines

    # 3. Get calibration text using scraped website content as the raw context
    print("\nSTEP 3: GETTING CALIBRATION SAMPLE TEXT")
    calibration_data = get_calibration_sample_text(auth_token, presentation_id, topic)
    sample_text = None
    default_verbosity = 3
    if calibration_data and isinstance(calibration_data, dict) and "sample_text" in calibration_data:
        sample_text = calibration_data.get("sample_text")
        default_verbosity = calibration_data.get("verbosity_level", 3)
        print("Using sample text from API.")
    else:
        print("Failed to get calibration sample text from API. Using fallback sample text.")
        sample_text = ("Sample fallback text for calibration. Adjust this text as needed for verbosity calibration.")

    # 4. Calibrate verbosity
    print("\nSTEP 4: CALIBRATING VERBOSITY")
    target_verbosity = 4
    tone = "PROFESSIONAL"
    print(f"Attempting to calibrate to verbosity level {target_verbosity} and tone {tone}")
    verbosity_result = calibrate_verbosity(auth_token, presentation_id, sample_text, target_verbosity, default_verbosity, tone)
    if verbosity_result:
        print("Verbosity calibration request sent successfully.")
    else:
        print("Verbosity calibration request failed.")

    # 5. Generate slide variants for the first slide
    print("\nSTEP 5: GENERATING SLIDE VARIANTS FOR FIRST SLIDE")
    if not first_slide_id:
        print("Missing first slide ID. Cannot generate variants. Exiting.")
        exit(1)
    
    variants = stream_slide_variants(
        auth_token, 
        presentation_id, 
        first_slide_id, 
        selected_outlines[0], 
        starting_slide_order=0
    )
    
    if not variants:
        print("Failed to generate slide variants for first slide. Check variants_ws_messages.log. Exiting.")
        exit(1)

    # Choose the 4th variant if available, else fallback to the last variant
    if len(variants) >= 4:
        variant_to_set = variants[3]
    else:
        variant_to_set = variants[-1]
    
    print("\nSTEP 6: SETTING ACTIVE VARIANT FOR FIRST SLIDE")
    variant_id = variant_to_set.get("variant_id")
    
    if not variant_id:
        print("Could not find variant ID in the selected variant. Exiting.")
        exit(1)
    
    set_active_result = set_active_variant(auth_token, first_slide_id, variant_id)
    if set_active_result:
        print(f"Successfully set active variant {variant_id} for slide {first_slide_id}")
    else:
        print("Failed to set active variant for first slide.")

    print("\nSTEP 7: PROCESSING REMAINING OUTLINES")
    slide_order = 2
    for outline in selected_outlines[1:]:
        print(f"\n--- Processing outline: {outline.get('heading', 'No Heading')} ---")
        new_slide_id = create_new_slide(auth_token, presentation_id, slide_order)
        if not new_slide_id:
            print("Failed to create new slide. Skipping to next outline.")
            slide_order += 1
            continue

        new_variants = stream_slide_variants(
            auth_token, 
            presentation_id, 
            new_slide_id, 
            outline, 
            starting_slide_order=slide_order
        )
        if not new_variants:
            print("Failed to generate slide variants for the new slide. Skipping to next outline.")
            slide_order += 1
            continue


        if len(new_variants) >= 4:
            variant_to_set = new_variants[3]
        else:
            variant_to_set = new_variants[-1]
        new_variant_id = variant_to_set.get("variant_id")
        if not new_variant_id:
            print("Could not find variant ID for new slide. Skipping to next outline.")
            slide_order += 1
            continue

        set_active_result = set_active_variant(auth_token, new_slide_id, new_variant_id)
        if set_active_result:
            print(f"Successfully set active variant {new_variant_id} for new slide {new_slide_id}")
        else:
            print("Failed to set active variant for new slide.")

        slide_order += 1

    print("\n==== PRESENTATION GENERATION COMPLETE ====")
    
    share_url = "https://alai-standalone-backend.getalai.com/upsert-presentation-share"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }
    payload = {
        "presentation_id": presentation_id
    }
    try:
        response = requests.post(share_url, headers=headers, json=payload)
        response.raise_for_status()
        share_str = response.text.strip()
        share_str = share_str.strip('"')
        final_url = f"https://app.getalai.com/view/{share_str}"
        print(final_url)
    except requests.exceptions.RequestException as e:
        print(f"Error calling presentation share endpoint: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Response: {e.response.text}")
