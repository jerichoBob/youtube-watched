"""
Demostrate output validator.

@dev You need to add OPENAI_API_KEY to your environment variables.
"""

import os
import sys
import json
import asyncio
import traceback
from typing import Any
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from browser_use import Agent, ActionResult, AgentHistoryList, Controller

load_dotenv('.env.local')

# Initialize the controller
controller = Controller()

class DoneResult(BaseModel):
    title: str
    comments: str
    hours_since_start: int
    
    def __str__(self) -> str:
        return json.dumps({
            'title': self.title,
            'comments': self.comments,
            'hours_since_start': self.hours_since_start
        })
    
    def __repr__(self) -> str:
        return self.__str__()

# we overwrite done() in this example to demonstrate the validator
@controller.registry.action('Done with task', param_model=DoneResult)
async def done(params: DoneResult):
    # Convert DoneResult to JSON string for ActionResult
    result = ActionResult(is_done=True, extracted_content=params.model_dump_json())
    print(result)
    return result

def pretty_print_agent_history(history: Any) -> None:
    """Pretty print the agent history with actions and model outputs.
    
    Args:
        history: AgentHistory object containing the execution history
    """
    print("\n=== Agent Execution History ===")
    print(history)
    print("-"*40)
    print(f"\nObject type: {type(history)}")
    if isinstance(history, dict):
        print("Top-level keys:")
        for key in history.keys():
            print(f"  - {key}")
    elif isinstance(history, AgentHistoryList):
        history_array = history.history
        print("\nhistory_array:")
        for i, result in enumerate(history_array, 1):
            print(f"  - Step {i}: {result}")
            print("-"*40)
        print(f"Number of elements in history_array: {len(history_array)}")
    return

    # Print actions taken
    print("\n🔄 Actions Results:")
    for i, result in enumerate(history.result, 1):
        print(f"\n  Step {i}:")
        print(f"    Done: {'✅' if result.is_done else '❌'}")
        
        # Try to parse JSON content if present
        try:
            content = json.loads(result.extracted_content)
            print(f"    Content: {json.dumps(content, indent=6)}")
        except:
            print(f"    Content: {result.extracted_content}")
        
        if result.error:
            print(f"    Error: {result.error}")
    
    # Print model output if present
    if history.model_output:
        print("\n🤖 Model Output:")
        print(f"  Current State: {history.model_output.current_state}")
        
        print("\n  Actions:")
        for i, action in enumerate(history.model_output.action, 1):
            print(f"\n    Action {i}:")
            action_dump = action.model_dump(exclude_none=True)
            for key, value in action_dump.items():
                print(f"      {key}: {json.dumps(value, indent=6) if isinstance(value, dict) else value}")
    
    # Print browser state
    if history.state:
        print("\n🌐 Browser State:")
        state_dict = history.state.to_dict()
        for key, value in state_dict.items():
            if isinstance(value, dict):
                print(f"\n  {key}:")
                print(json.dumps(value, indent=4))
            else:
                print(f"  {key}: {value}")


def parse_dom_element(element_str: str) -> dict:
    """Parse a DOM element string into a dictionary."""
    element_dict = {}
    
    # Handle DOMHistoryElement format
    if "DOMHistoryElement" in element_str:
        element_str = element_str[element_str.find("DOMHistoryElement(") + len("DOMHistoryElement("):]
        element_str = element_str.rstrip(")")
    
    # Extract coordinates if present
    if "coordinates=" in element_str:
        coords_str = element_str[element_str.find("coordinates=") + len("coordinates="):]
        coords_end = coords_str.find(")")
        if coords_end != -1:
            coords = coords_str[:coords_end].strip("()")
            try:
                x, y = map(float, coords.split(","))
                element_dict["coordinates"] = {"x": x, "y": y}
            except:
                pass
    
    # Extract CSS selectors
    if "css_selectors=" in element_str:
        selectors_str = element_str[element_str.find("css_selectors=") + len("css_selectors="):]
        selectors_end = selectors_str.find(",")
        if selectors_end != -1:
            selectors = selectors_str[:selectors_end].strip("[]'")
            element_dict["css_selectors"] = selectors.split(", ")
    
    # Extract text content
    if "text_content=" in element_str:
        text_str = element_str[element_str.find("text_content='") + len("text_content='"):]
        text_end = text_str.find("'")
        if text_end != -1:
            element_dict["text_content"] = text_str[:text_end]
    
    # Extract tag name
    if "tag_name=" in element_str:
        tag_str = element_str[element_str.find("tag_name='") + len("tag_name='"):]
        tag_end = tag_str.find("'")
        if tag_end != -1:
            element_dict["tag_name"] = tag_str[:tag_end]
    
    # Extract attributes
    if "attributes=" in element_str:
        attrs_str = element_str[element_str.find("attributes=") + len("attributes="):]
        attrs_end = attrs_str.find("}")
        if attrs_end != -1:
            attrs = attrs_str[:attrs_end + 1]
            try:
                element_dict["attributes"] = eval(attrs)
            except:
                pass
    
    # Extract is_visible
    if "is_visible=" in element_str:
        vis_str = element_str[element_str.find("is_visible=") + len("is_visible="):]
        vis_end = vis_str.find(",")
        if vis_end != -1:
            element_dict["is_visible"] = vis_str[:vis_end].strip() == "True"
    
    # Extract is_enabled
    if "is_enabled=" in element_str:
        enabled_str = element_str[element_str.find("is_enabled=") + len("is_enabled="):]
        enabled_end = enabled_str.find(",")
        if enabled_end != -1:
            element_dict["is_enabled"] = enabled_str[:enabled_end].strip() == "True"
    
    # Extract page coordinates
    if "page_coordinates=" in element_str:
        coords_str = element_str[element_str.find("page_coordinates=") + len("page_coordinates="):]
        coords_end = coords_str.find(")")
        if coords_end != -1:
            coords = coords_str[:coords_end].strip("()")
            try:
                x, y = map(float, coords.split(","))
                element_dict["page_coordinates"] = {"x": x, "y": y}
            except:
                pass
    
    # Extract viewport coordinates
    if "viewport_coordinates=" in element_str:
        coords_str = element_str[element_str.find("viewport_coordinates=") + len("viewport_coordinates="):]
        coords_end = coords_str.find(")")
        if coords_end != -1:
            coords = coords_str[:coords_end].strip("()")
            try:
                x, y = map(float, coords.split(","))
                element_dict["viewport_coordinates"] = {"x": x, "y": y}
            except:
                pass
    
    # Extract viewport info
    if "viewport_info=" in element_str:
        viewport_str = element_str[element_str.find("viewport_info=") + len("viewport_info="):]
        viewport_end = viewport_str.find(")")
        if viewport_end != -1:
            viewport_str = viewport_str[:viewport_end].strip("()")
            try:
                info = {}
                for part in viewport_str.split(", "):
                    if "=" in part:
                        key, value = part.split("=")
                        info[key.strip()] = int(value)
                element_dict["viewport_info"] = info
            except:
                pass
    
    return element_dict


def format_dom_element(element_dict: dict, indent: str = "") -> str:
    """Format a DOM element dictionary into a readable string."""
    output = []
    
    if "tag_name" in element_dict:
        output.append(f"{indent}Tag: {element_dict['tag_name']}")
    
    if "text_content" in element_dict:
        output.append(f"{indent}Text: {element_dict['text_content']}")
    
    if "coordinates" in element_dict:
        coords = element_dict["coordinates"]
        output.append(f"{indent}Coordinates: x={coords['x']}, y={coords['y']}")
    
    if "page_coordinates" in element_dict:
        coords = element_dict["page_coordinates"]
        output.append(f"{indent}Page Coordinates: x={coords['x']}, y={coords['y']}")
    
    if "viewport_coordinates" in element_dict:
        coords = element_dict["viewport_coordinates"]
        output.append(f"{indent}Viewport Coordinates: x={coords['x']}, y={coords['y']}")
    
    if "viewport_info" in element_dict:
        info = element_dict["viewport_info"]
        output.append(f"{indent}Viewport Info:")
        for key, value in info.items():
            output.append(f"{indent}  {key}: {value}")
    
    if "css_selectors" in element_dict:
        output.append(f"{indent}CSS Selectors:")
        for selector in element_dict["css_selectors"]:
            output.append(f"{indent}  - {selector}")
    
    if "attributes" in element_dict:
        output.append(f"{indent}Attributes:")
        for key, value in element_dict["attributes"].items():
            output.append(f"{indent}  {key}: {value}")
    
    if "is_visible" in element_dict:
        output.append(f"{indent}Visible: {element_dict['is_visible']}")
    
    if "is_enabled" in element_dict:
        output.append(f"{indent}Enabled: {element_dict['is_enabled']}")
    
    return "\n".join(output)


def parse_agent_history(history_str: str) -> None:
    """Parse and display the agent history results in a readable format."""
    print("\n=== Agent History Results ===")
    
    # Extract the lists using string manipulation since we have a string representation
    if isinstance(history_str, str):
        # Find the results list
        results_start = history_str.find("all_results=[") + len("all_results=[")
        results_end = history_str.find("], all_model_outputs=")
        results_str = history_str[results_start:results_end]
        
        # Find the model outputs list
        outputs_start = history_str.find("all_model_outputs=[") + len("all_model_outputs=[")
        outputs_end = history_str.find("])", outputs_start)
        outputs_str = history_str[outputs_start:outputs_end]
        
        # Parse results
        print("\n🔄 Actions Sequence:")
        results = []
        current_result = ""
        depth = 0
        
        # Parse results more carefully to handle nested structures
        for char in results_str:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0:
                    results.append(current_result + char)
                    current_result = ""
                    continue
            
            if depth > 0 or char.strip():
                current_result += char
        
        for i, result in enumerate(results, 1):
            if not result.strip():  # Skip empty results
                continue
                
            print(f"\nStep {i}:")
            # Clean up the ActionResult string
            result = result.strip()
            if result.startswith("ActionResult("):
                result = result[len("ActionResult("):].rstrip(")")
            
            # Parse key-value pairs more carefully
            result_dict = {}
            key = ""
            value = ""
            in_value = False
            quote_char = None
            
            for char in result + ",":  # Add comma to handle last pair
                if not in_value:
                    if char == "=":
                        in_value = True
                        key = key.strip()
                    else:
                        key += char
                else:
                    if quote_char:
                        if char == quote_char:
                            quote_char = None
                        value += char
                    elif char in ["'", '"']:
                        quote_char = char
                        value += char
                    elif char == "," and not quote_char:
                        result_dict[key] = value.strip()
                        key = ""
                        value = ""
                        in_value = False
                    else:
                        value += char
            
            print(f"  Status: {'✅ Done' if result_dict.get('is_done') == 'True' else '⏳ In Progress'}")
            
            if result_dict.get('error') and result_dict['error'] != 'None':
                print(f"  ❌ Error: {result_dict['error']}")
            elif result_dict.get('extracted_content') and result_dict['extracted_content'] != 'None':
                content = result_dict['extracted_content'].strip("'")
                try:
                    # Try to parse as JSON
                    json_content = json.loads(content)
                    if isinstance(json_content, dict):
                        print("  Content:")
                        for key, value in json_content.items():
                            print(f"    {key}: {value}")
                    else:
                        print(f"  Content: {json_content}")
                except:
                    print(f"  Content: {content}")
        
        # Parse model outputs
        print("\n🤖 Model Actions:")
        outputs = []
        current_output = ""
        depth = 0
        
        # Parse outputs more carefully to handle nested structures
        for char in outputs_str:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    outputs.append(current_output + char)
                    current_output = ""
                    continue
            
            if depth > 0 or char.strip():
                current_output += char
        
        action_num = 1
        for output in outputs:
            if not output.strip():  # Skip empty outputs
                continue
                
            print(f"\nAction {action_num}:")
            action_num += 1
            
            # Clean up and parse the output
            output = output.strip()
            if output.startswith("{"):
                output = output[1:]
            if output.endswith("}"):
                output = output[:-1]
            
            # Try to parse as a dictionary
            try:
                # Convert single quotes to double quotes for JSON parsing
                json_str = output.replace("'", '"')
                output_dict = json.loads("{" + json_str + "}")
                
                for action_type, params in output_dict.items():
                    if action_type == 'interacted_element':
                        if params:
                            print("\n  🎯 Element Details:")
                            element_dict = parse_dom_element(str(params))
                            print(format_dom_element(element_dict, "    "))
                    else:
                        print(f"  {action_type}:")
                        if isinstance(params, dict):
                            for key, value in params.items():
                                print(f"    {key}: {value}")
                        else:
                            print(f"    {params}")
            except Exception as e:
                print(f"  Parse Error: {e}")
                # Try to extract action type and parameters
                for action_type in ['open_tab', 'click_element', 'done']:
                    if f"'{action_type}'" in output:
                        print(f"  {action_type}:")
                        try:
                            params_start = output.find(f"'{action_type}': ") + len(f"'{action_type}': ")
                            params_end = output.find(", '", params_start)
                            if params_end == -1:
                                params_end = len(output)
                            params_str = output[params_start:params_end]
                            print(f"    Raw: {params_str}")
                        except:
                            print(f"    Raw: {output}")


async def main():
    """Main entry point."""
    try:
        task = 'Go to https://news.ycombinator.com/ and give me the top post'
        model = ChatOpenAI(model='gpt-4o')
        agent = Agent(task=task, llm=model, controller=controller, validate_output=False)
        result = await agent.run(max_steps=5)
        
        print('---')
        parse_agent_history(str(result))
        
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())