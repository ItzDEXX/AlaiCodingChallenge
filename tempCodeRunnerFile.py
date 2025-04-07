import requests
import json
import uuid
import os
import time
from dotenv import load_dotenv
import websocket
import threading

load_dotenv()

# --- API Functions ---

def create_new_presentation(auth_token):
    """Creates a new presentation and returns its data, including the first slide if created."""
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

def generate_slides_outline(auth_token, presentation_id, topic, instructions):
    """Connect to WebSocket to generate slides outline based on topic and instructions."""
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
            
            # Handle slide outline in the format from your payload
            if isinstance(data, dict) and "slide_outline" in data:
                outline_data = {
                    "heading": data["slide_outline"].get("slide_title", "No title"),
                    "slide_context": data["slide_outline"].get("slide_context", ""),
                    "slide_instructions": data["slide_outline"].get("slide_instructions", "")
                }
                print(f"Received outline with heading: {outline_data['heading']}")
                outlines.append(outline_data)
            # Original format handling
            elif isinstance(data, dict) and "heading" in data and "slide_context" in data:
                print(f"Received single outline object: {data.get('heading')}")
                outlines.append(data)
            elif isinstance(data, list) and all("heading" in item for item in data):
                print(f"Received {len(data)} outlines directly in a list.")
                outlines = data
            elif isinstance(data, dict) and "outlines" in data and isinstance(data["outlines"], list):
                print(f"Received {len(data['outlines'])} outlines within a dictionary.")
                outlines = data["outlines"]
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
            try: ws.close()
            except Exception as e: print(f"Error during final close: {e}")
        wst.join(timeout=2)
        if wst.is_alive(): print("Warning: Outline WebSocket thread did not exit gracefully.")
    
    try:
        try:
            parsed_messages = [json.loads(msg) for msg in ws_messages]
            with open("outline_ws_messages.log", "w") as f: json.dump(parsed_messages, f, indent=2)
        except json.JSONDecodeError:
            print("Could not parse all outline WS messages as JSON, saving raw.")
            with open("outline_ws_messages.log", "w") as f:
                for msg in ws_messages: f.write(msg + "\n")
        print("Outline WebSocket messages saved to outline_ws_messages.log")
    except Exception as e: print(f"Error saving outline WS messages: {e}")
    
    print("\n===== DETAILED OUTLINES =====")
    for i, outline in enumerate(outlines):
        print(f"\nOUTLINE {i+1}:")
        print(f"Heading: {outline.get('heading', 'No heading')}")
        print(f"Context: {outline.get('slide_context', 'No context')}")
        print(f"Instructions: {outline.get('slide_instructions', 'No instructions')}")
    print("\n============================")
    
    return outlines

def get_calibration_sample_text(auth_token, presentation_id, raw_context):
    """Fetches sample text for verbosity calibration."""
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
    """Sends verbosity calibration request."""
    url = "https://alai-standalone-backend.getalai.com/calibrate-verbosity"
    headers = { "Content-Type": "application/json", "Accept": "application/json", "Authorization": f"Bearer {auth_token}" }
    payload = { "original_text": original_text, "presentation_id": presentation_id, "verbosity_level": verbosity_level, "tone_type": tone_type }
    if previous_verbosity_level is not None: payload["previous_verbosity_level"] = previous_verbosity_level
    if tone_instructions is not None: payload["tone_instructions"] = tone_instructions
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

def create_slides_from_outlines(auth_token, presentation_id, slide_id, slide_outlines, instructions, context, starting_slide_order=0):
    """Connect to WebSocket to create slides from outlines."""
    ws_url = f"wss://alai-standalone-backend.getalai.com/ws/create-slides-from-outlines?token={auth_token}"
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
            
            # Case 1: Direct variant with variant_id
            if isinstance(data, dict) and "variant_id" in data:
                print(f"Received variant with ID: {data.get('variant_id')}")
                variants.append(data)
            
            # Case 2: Message containing slide with variants array
            elif isinstance(data, dict) and "id" in data and "slide_id" in data and "element_slide" in data:
                variant_id = data.get("id")
                slide_id = data.get("slide_id")
                print(f"Received variant {variant_id} for slide {slide_id}")
                
                # Store the variant with essential information
                variant_info = {
                    "variant_id": variant_id,
                    "slide_id": slide_id,
                    "slide_content": data.get("element_slide", {})
                }
                variants.append(variant_info)
            
            # Case 3: Presentation or slide update with no variants
            elif isinstance(data, dict) and "id" in data and (
                "presentation_title" in data or 
                ("presentation_id" in data and "slide_order" in data and "variants" in data)
            ):
                print(f"Received presentation/slide update (not a variant): {data['id']}")
                
                # Check if this is a slide with variants
                if "variants" in data and isinstance(data["variants"], list) and data["variants"]:
                    print(f"Found {len(data['variants'])} variants in slide update")
                    for variant in data["variants"]:
                        if isinstance(variant, dict) and "id" in variant:
                            variant_info = {
                                "variant_id": variant["id"],
                                "slide_id": data["id"],
                                "slide_content": variant.get("element_slide", {})
                            }
                            variants.append(variant_info)
            
            # Case 4: Array of variants
            elif isinstance(data, list):
                valid_variants = [item for item in data if isinstance(item, dict) and "id" in item]
                if valid_variants:
                    print(f"Received {len(valid_variants)} variants in a list")
                    for variant in valid_variants:
                        variant_info = {
                            "variant_id": variant["id"],
                            "slide_id": variant.get("slide_id", slide_id),  # Use passed slide_id if not in variant
                            "slide_content": variant.get("element_slide", {})
                        }
                        variants.append(variant_info)
            
            else:
                print(f"Received message in unexpected format: {message[:100]}...")
                
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON in variants WS: {e}")
        except Exception as e:
            print(f"Error processing variants message: {e}")
            print(f"Exception details: {str(e)}")
    
    def on_error(ws, error):
        nonlocal ws_error
        print(f"Variants WebSocket error: {error}")
        ws_error = error
        connection_closed.set()
    
    def on_close(ws, close_status_code, close_msg):
        print(f"Variants WebSocket connection closed. Status code: {close_status_code}, Message: {close_msg}")
        connection_closed.set()
    
    def on_open(ws):
        print("Variants WebSocket connection opened for creating slides")
        request_data = {
            "auth_token": auth_token,
            "presentation_id": presentation_id,
            "presentation_instructions": instructions,
            "raw_context": context,
            "slide_id": slide_id,
            "slide_outlines": slide_outlines,
            "starting_slide_order": starting_slide_order,
            "update_tone_verbosity_calibration_status": True
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
    timeout = 120  # Longer timeout for variants generation
    connection_closed.wait(timeout=timeout)
    
    if ws_error:
        print("Variants generation failed due to WebSocket error.")
    elif not variants:
        print("Variants connection closed or timed out without receiving valid variants.")
    
    if wst.is_alive():
        if ws.sock and ws.sock.connected:
            try: ws.close()
            except Exception as e: print(f"Error during final close: {e}")
        wst.join(timeout=2)
        if wst.is_alive(): print("Warning: Variants WebSocket thread did not exit gracefully.")
    
    try:
        try:
            with open("variants_ws_messages_raw.log", "w") as f:
                for msg in ws_messages: f.write(msg + "\n")
            
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
    """Sets the active variant for a slide."""
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

def update_slide_entity(auth_token, slide_data):
    """Updates slide entity with new data."""
    url = "https://alai-standalone-backend.getalai.com/update-slide-entity"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }
    
    # Generate a unique slide ID if not provided
    if "id" not in slide_data or not slide_data["id"]:
        slide_data["id"] = str(uuid.uuid4())
    
    # Format created_at as ISO 8601 timestamp with timezone if not present
    if "created_at" not in slide_data:
        from datetime import datetime, timezone
        current_time = datetime.now(timezone.utc)
        slide_data["created_at"] = current_time.isoformat()
    
    # Ensure other required fields are present
    if "presentation_context" not in slide_data:
        slide_data["presentation_context"] = None
    
    # Format slide_outline based on the expected payload format
    # Add this field to the slide_outline object
    if "slide_outline" in slide_data:
        # Add image_on_slide field if it doesn't exist
        if "image_on_slide" not in slide_data["slide_outline"]:
            slide_data["slide_outline"]["image_on_slide"] = None
        if "slide_context" not in slide_data["slide_outline"] and "slide_context" in slide_data:
            slide_data["slide_outline"]["slide_context"] = slide_data["slide_context"]
        
        if "slide_instructions" not in slide_data["slide_outline"] and "slide_instructions" in slide_data:
            slide_data["slide_outline"]["slide_instructions"] = slide_data["slide_instructions"]
        
        if "slide_id" not in slide_data["slide_outline"]:
            slide_data["slide_outline"]["slide_id"] = slide_data["id"]
        
        # Rename heading to slide_title if needed
        if "heading" in slide_data["slide_outline"]:
            slide_data["slide_outline"]["slide_title"] = slide_data["slide_outline"].pop("heading")
        
        # Rename content to slide_context if needed
        if "content" in slide_data["slide_outline"]:
            slide_data["slide_outline"]["slide_context"] = slide_data["slide_outline"].pop("content")
    # Create slide_outline if not present
    elif "heading" in slide_data or "slide_context" in slide_data:
        slide_outline_id = str(uuid.uuid4())
        slide_data["slide_outline"] = {
            "id": slide_outline_id,
            "created_at": slide_data["created_at"],
            "slide_id": slide_data["id"],
            "slide_title": slide_data.pop("heading", "New Slide"),
            "slide_context": slide_data.get("slide_context", ""),
            "slide_instructions": slide_data.get("slide_instructions", "")
        }
    
    try:
        print(f"Updating slide entity with payload: {json.dumps(slide_data, indent=2)}")
        response = requests.post(url, headers=headers, json=slide_data)
        response.raise_for_status()
        result = response.json()
        print(f"Successfully updated slide entity! Response: {json.dumps(result, indent=2)}")
        return result
    except requests.exceptions.RequestException as e:
        print(f"Error updating slide entity: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Response: {e.response.text}")
        return None

def create_slides_from_outlines_main(auth_token, presentation_id, outlines, instructions, topic):
    """Main function to create slides from outlines."""
    successful_slides = []

    # Skip the first outline since we already have the first slide
    for i, outline in enumerate(outlines[1:], start=1):
        new_slide_id = str(uuid.uuid4())
        slide_outline_id = str(uuid.uuid4())
        
        from datetime import datetime, timezone
        current_time = datetime.now(timezone.utc)
        created_at = current_time.isoformat()
        
        slide_data = {
            "id": new_slide_id,
            "presentation_id": presentation_id,
            "slide_order": i + 1,  # +1 because we're skipping the first slide
            "color_set_id": 0,
            "slide_status": "DEFAULT",
            "active_variant_id": None,
            "created_at": created_at,
            "presentation_context": None,
            "slide_context": outline.get("slide_context", ""),
            "slide_instructions": outline.get("slide_instructions", ""),
            "slide_outline": {
                "id": slide_outline_id,
                "created_at": created_at,
                "slide_id": new_slide_id,
                "slide_title": outline.get("heading", f"Slide {i+1}"),
                "slide_context": outline.get("slide_context", ""),
                "slide_instructions": outline.get("slide_instructions", "")
            },
            "variants": []
        }
        
        print(f"Creating slide {i+1} with heading: {slide_data['slide_outline']['slide_title']}")
        update_result = update_slide_entity(auth_token, slide_data)
        
        if update_result:
            print(f"Successfully created slide with ID: {update_result.get('id')}")
            successful_slides.append(update_result)
            
            # Generate variants for this slide
            print(f"Generating variants for slide {i+1}...")
            variants = create_slides_from_outlines(
                auth_token,
                presentation_id,
                new_slide_id,
                [outline],  # Just use the current outline
                instructions,
                topic,
                starting_slide_order=i+1
            )
            
            # If variants were generated, set the active variant
            if variants and len(variants) > 0:
                last_variant = variants[-1]
                variant_id = last_variant.get("variant_id")
                
                if variant_id:
                    print(f"Setting active variant for slide {i+1}...")
                    set_active_result = set_active_variant(auth_token, new_slide_id, variant_id)
                    if set_active_result:
                        print(f"Successfully set active variant {variant_id} for slide {new_slide_id}")
                    else:
                        print(f"Failed to set active variant for slide {i+1}")
        else:
            print(f"Failed to create slide {i+1}")

    print(f"\nSuccessfully created {len(successful_slides)} additional slides from outlines")
    return successful_slides


# --- Main Execution Logic ---
if __name__ == "__main__":
    auth_token = os.getenv("AUTH_TOKEN")
    if not auth_token:
        print("AUTH_TOKEN environment variable not found. Please create a .env file with AUTH_TOKEN='your_token'")
        exit(1)

    print("Starting presentation generation process...")

    # 1. Create presentation
    print("\n==== STEP 1: CREATE NEW PRESENTATION ====")
    presentation_data = create_new_presentation(auth_token)
    if not presentation_data or "id" not in presentation_data: exit(1)
    presentation_id = presentation_data.get("id")
    first_slide_id = None
    if presentation_data.get("slides") and isinstance(presentation_data["slides"], list) and len(presentation_data["slides"]) > 0:
        first_slide = presentation_data["slides"][0]
        if isinstance(first_slide, dict) and "id" in first_slide: first_slide_id = first_slide.get("id")
    print(f"Created presentation with ID: {presentation_id}")
    if first_slide_id: print(f"Detected first slide ID: {first_slide_id}")
    else: print("Warning: Could not detect ID of the initially created slide.")

    # 2. Generate outlines (Using specific example values)
    topic = "World War 3 Possibilities"  # Example topic - change as needed
    instructions = "Focus on geopolitical tensions and historical parallels"  # Example instructions - change as needed
    print(f"\n==== STEP 2: GENERATING OUTLINES FOR TOPIC: '{topic}' ====")
    outlines = generate_slides_outline(auth_token, presentation_id, topic, instructions)
    if not outlines:
        print("Failed to generate outlines. Check outline_ws_messages.log. Exiting.")
        exit(1)
    print(f"\nGenerated {len(outlines)} outlines:")
    for i, outline in enumerate(outlines): print(f"- {outline.get('heading', f'Outline {i+1}')}")
    selected_outlines = outlines

    # 3. Get calibration text
    print("\n==== STEP 3: GETTING CALIBRATION SAMPLE TEXT ====")
    calibration_data = get_calibration_sample_text(auth_token, presentation_id, topic)
    sample_text = None
    default_verbosity = 3
    if calibration_data and isinstance(calibration_data, dict) and "sample_text" in calibration_data:
        sample_text = calibration_data.get("sample_text")
        default_verbosity = calibration_data.get("verbosity_level", 3)
        print("Using sample text from API.")
    else:
        print("Failed to get calibration sample text from API. Skipping calibration step.")
        sample_text = "• Geopolitical tensions between major powers\n• Nuclear proliferation concerns\n• Regional conflicts with global implications\n• Cyber warfare capabilities\n• Resource competition"
        print("Using fallback sample text.")

    # 4. Calibrate verbosity
    print("\n==== STEP 4: CALIBRATING VERBOSITY ====")
    target_verbosity = 4
    tone = "PROFESSIONAL"
    print(f"Attempting to calibrate to verbosity level {target_verbosity} and tone {tone}")
    verbosity_result = calibrate_verbosity(auth_token, presentation_id, sample_text, target_verbosity, default_verbosity, tone)
    if verbosity_result: print("Verbosity calibration request sent successfully.")
    else: print("Verbosity calibration request failed.")
    
    # 5. Generate slide variants for the first slide
    print("\n==== STEP 5: GENERATING SLIDE VARIANTS FOR FIRST SLIDE ====")
    if not first_slide_id:
        print("Missing first slide ID. Cannot generate variants. Exiting.")
        exit(1)
    
    variants = create_slides_from_outlines(
        auth_token, 
        presentation_id, 
        first_slide_id, 
        selected_outlines[:1],  # Using first outline for the first slide
        instructions, 
        topic
    )
    
    if not variants:
        print("Failed to generate slide variants. Check variants_ws_messages.log. Exiting.")
        exit(1)
    
    # 6. Set active variant for the first slide
    print("\n==== STEP 6: SETTING ACTIVE VARIANT FOR FIRST SLIDE ====")
    last_variant = variants[-1]
    variant_id = last_variant.get("variant_id")
    
    if not variant_id:
        print("Could not find variant ID in the last variant. Exiting.")
        exit(1)
    
    set_active_result = set_active_variant(auth_token, first_slide_id, variant_id)
    if set_active_result:
        print(f"Successfully set active variant {variant_id} for slide {first_slide_id}")
    else:
        print("Failed to set active variant.")
    
    # 7. Create the rest of the slides from outlines
    print("\n==== STEP 7: CREATING SLIDES FROM OUTLINES ====")
    successful_slides = create_slides_from_outlines_main(
        auth_token, 
        presentation_id, 
        selected_outlines, 
        instructions, 
        topic
    )
    
    print("\n==== PRESENTATION GENERATION COMPLETE ====")
    print(f"Created presentation with ID: {presentation_id}")
    print(f"Total slides created: {len(successful_slides) + 1}")  # +1 for the first slide
    print("You can now access your presentation in the ALAI interface.")