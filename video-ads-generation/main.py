import os
import asyncio
from dotenv import load_dotenv
from typing import Annotated, TypedDict
from video_gen import start_video_generation, wait_for_completion
from utils import log_to_excel, ainvoke_llm, get_current_date
from prompt_library import PROMPT_LIBRARY


# Models for structured outputs
class VideoDetails(TypedDict):
    title: str = Annotated[str, "Title of the video"]
    prompt: str = Annotated[str, "Prompt for the video"]

async def generate_veo3_video_prompt(ad_idea: str, inspiration_prompt: str):
    print(f"Creating video prompt for creative idea: '{ad_idea}'...")
    system_prompt = """
Edit a structured prompt object (JSON) based on the provided user creative idea.  

# Instructions:
- Adapt the inspiration prompt to the user creative direction including style, room, background, elements, motion, ending, text, keywords
- Do not modify any part of the structure unless the user explicitly requests it.
- Maintain original structure and intention unless asked otherwise.

# **Output**: Your response should be in the following structure:

```json
{
    "title": "Title of the video",
    "prompt": "Prompt for the video"
}
```
"""
    
    user_message = (
        f"Video Idea: {ad_idea}"
        f"Follow and get instructions directly from this prompt:\n\n{inspiration_prompt}"
    )
    
    # Use the AI invocation function
    result = await ainvoke_llm(
        model="gpt-4.1",
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=0.3,
        response_format=VideoDetails
    )
    return result


async def run_workflow(inputs):
    try:
        # Create a log entry for excel
        log_entry = {
            'title': "",
            'prompt': "",
            'status': "in_progress",
            'created_at': get_current_date(),
            'video_url': None
        }
    
        # Generate V3 prompt
        video_details = await generate_veo3_video_prompt(inputs['ad_idea'], inputs['inspiration_prompt'])
        log_entry['title'] = video_details['title']
        log_entry['prompt'] = video_details['prompt']
        
        # Log the initial entry and get the row index
        row_index = log_to_excel(log_entry)
        print(f"Log entry created with index: {row_index}")
        
        # Submit to kie.ai
        taskid = start_video_generation(
            video_details['prompt'],
            inputs['aspect_ratio'],
            inputs['model']
        )
        if not taskid:
            log_entry['status'] = "failed"
            log_entry['error'] = "Failed to get request ID"
            # Update the existing row with error information
            log_to_excel(log_entry, row_index)
            return None
        
        log_entry['task_id'] = taskid
        
        # Update the log with request ID
        log_to_excel(log_entry, row_index)
        
        # Wait for completion
        result = wait_for_completion(taskid)
            
        # Update status and log results
        if result.get("status") == "failed":
            log_entry['status'] = "failed"
            log_entry['error'] = result.get("error", "Unknown error")
        else:
            log_entry['status'] = "completed"
            video_url = result.get("response", {}).get("resultUrls", [])
            log_entry['video_url'] = video_url[0] if video_url else ""
            print(f"Video URL: {video_url}")
        
        # Update the Excel log with final results
        log_to_excel(log_entry, row_index)
        
        return {
            "title": log_entry['title'],
            "prompt": log_entry['prompt'],
            "video_url": log_entry['video_url']
        }
    except Exception as e:
        print(f"Error in workflow: {str(e)}")
        return None
    

if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv()
    
    # Check if KIE_API_TOKEN environment variable is set
    if not os.environ.get("KIE_API_TOKEN"):
        print("Warning: KIE_API_TOKEN environment variable not set")
        raise ValueError("KIE_API_TOKEN environment variable not set")
    
    # Check if OPENROUTER_API_KEY environment variable is set
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("Warning: OPENROUTER_API_KEY environment variable not set")
        raise ValueError("OPENROUTER_API_KEY environment variable not set")
    
    ad_idea = "I want an ad for the launch of the new Mercedes Formula 1 car"  # Example idea
    
    # Get a prompt from the prompts library list 
    prompt_id = -1 # Tesla showdown prompt
    inspiration_prompt = PROMPT_LIBRARY[prompt_id]['prompt']
    
    # Run main function
    inputs = {
        "ad_idea": ad_idea,
        "inspiration_prompt": inspiration_prompt,
        "aspect_ratio": "16:9", # or "9:16",
        "model": "veo3_fast" # Cheaper "veo3_fast" or high quality "veo3"
    }
    asyncio.run(run_workflow(inputs))