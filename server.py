#!/usr/bin/env python3
"""
GoHighLevel MCP Server
Provides Claude with full API access to GoHighLevel CRM
"""

import asyncio
import json
import os
import time
from collections import deque
from typing import Any, Sequence, Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize MCP server
app = Server("gohighlevel")

# Configuration
GHL_API_KEY = os.getenv("GHL_API_KEY")
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID")
GHL_BASE_URL = os.getenv("GHL_BASE_URL", "https://services.leadconnectorhq.com")

# Rate limiting (100 requests per 10 seconds)
rate_limit_window = deque()
RATE_LIMIT_MAX = 100
RATE_LIMIT_WINDOW_SECONDS = 10


class RateLimitError(Exception):
    """Raised when rate limit is exceeded"""
    pass


def check_rate_limit():
    """Check if we're within rate limits"""
    now = time.time()
    # Remove requests older than the window
    while rate_limit_window and rate_limit_window[0] < now - RATE_LIMIT_WINDOW_SECONDS:
        rate_limit_window.popleft()

    if len(rate_limit_window) >= RATE_LIMIT_MAX:
        raise RateLimitError("Rate limit exceeded. Please wait a moment.")

    rate_limit_window.append(now)


async def ghl_request(
    method: str,
    endpoint: str,
    params: Optional[dict] = None,
    json_data: Optional[dict] = None,
    retries: int = 3
) -> dict:
    """Make an HTTP request to the GoHighLevel API with retry logic"""

    if not GHL_API_KEY:
        return {"error": "GHL_API_KEY not configured. Please set it in your environment."}

    check_rate_limit()

    headers = {
        "Authorization": f"Bearer {GHL_API_KEY}",
        "Version": "2021-04-15",
        "Content-Type": "application/json"
    }

    url = f"{GHL_BASE_URL}{endpoint}"

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_data
                )

                # Handle rate limiting
                if response.status_code == 429:
                    if attempt < retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff
                        await asyncio.sleep(wait_time)
                        continue
                    return {"error": "Rate limit exceeded. Please try again later."}

                # Handle other errors
                if response.status_code >= 400:
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        error_detail = json.dumps(error_json, indent=2)
                    except:
                        pass

                    return {
                        "error": f"API Error (HTTP {response.status_code})",
                        "details": error_detail
                    }

                return response.json()

        except httpx.TimeoutException:
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return {"error": "Request timed out"}
        except Exception as e:
            return {"error": f"Request failed: {str(e)}"}

    return {"error": "Max retries exceeded"}


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available GoHighLevel tools"""
    return [
        # Contacts (12 tools)
        Tool(
            name="ghl_contacts_list",
            description="List/search contacts with filtering. Returns up to 100 contacts per page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"},
                    "query": {"type": "string", "description": "Search query (name, email, phone)"},
                    "limit": {"type": "integer", "description": "Number of results (max 100)", "default": 20},
                    "skip": {"type": "integer", "description": "Number of results to skip", "default": 0},
                    "tags": {"type": "string", "description": "Comma-separated tag IDs to filter by"},
                }
            }
        ),
        Tool(
            name="ghl_contacts_get",
            description="Get a specific contact by ID with all details",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"}
                },
                "required": ["contact_id"]
            }
        ),
        Tool(
            name="ghl_contacts_create",
            description="Create a new contact",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"},
                    "first_name": {"type": "string", "description": "First name"},
                    "last_name": {"type": "string", "description": "Last name"},
                    "email": {"type": "string", "description": "Email address"},
                    "phone": {"type": "string", "description": "Phone number"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Array of tag names"},
                    "custom_fields": {"type": "object", "description": "Custom field key-value pairs"},
                    "source": {"type": "string", "description": "Contact source"}
                }
            }
        ),
        Tool(
            name="ghl_contacts_update",
            description="Update an existing contact",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"},
                    "first_name": {"type": "string", "description": "First name"},
                    "last_name": {"type": "string", "description": "Last name"},
                    "email": {"type": "string", "description": "Email address"},
                    "phone": {"type": "string", "description": "Phone number"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Array of tag names"},
                    "custom_fields": {"type": "object", "description": "Custom field key-value pairs"}
                },
                "required": ["contact_id"]
            }
        ),
        Tool(
            name="ghl_contacts_delete",
            description="Delete a contact permanently",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"}
                },
                "required": ["contact_id"]
            }
        ),
        Tool(
            name="ghl_contacts_upsert",
            description="Create or update a contact based on email or phone (prevents duplicates)",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"},
                    "email": {"type": "string", "description": "Email address"},
                    "phone": {"type": "string", "description": "Phone number"},
                    "first_name": {"type": "string", "description": "First name"},
                    "last_name": {"type": "string", "description": "Last name"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Array of tag names"},
                    "custom_fields": {"type": "object", "description": "Custom field key-value pairs"}
                }
            }
        ),
        Tool(
            name="ghl_contacts_add_tags",
            description="Add tags to a contact",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Array of tag names to add"}
                },
                "required": ["contact_id", "tags"]
            }
        ),
        Tool(
            name="ghl_contacts_remove_tags",
            description="Remove tags from a contact",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Array of tag names to remove"}
                },
                "required": ["contact_id", "tags"]
            }
        ),
        Tool(
            name="ghl_contacts_add_note",
            description="Add a note to a contact",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"},
                    "body": {"type": "string", "description": "Note content"}
                },
                "required": ["contact_id", "body"]
            }
        ),
        Tool(
            name="ghl_contacts_get_notes",
            description="Get all notes for a contact",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"}
                },
                "required": ["contact_id"]
            }
        ),
        Tool(
            name="ghl_contacts_add_task",
            description="Create a task for a contact",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"},
                    "title": {"type": "string", "description": "Task title"},
                    "body": {"type": "string", "description": "Task description"},
                    "due_date": {"type": "string", "description": "Due date (ISO 8601 format)"},
                    "assigned_to": {"type": "string", "description": "User ID to assign task to"}
                },
                "required": ["contact_id", "title"]
            }
        ),
        Tool(
            name="ghl_contacts_get_tasks",
            description="Get all tasks for a contact",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"}
                },
                "required": ["contact_id"]
            }
        ),

        # Conversations/Messaging (8 tools)
        Tool(
            name="ghl_conversations_list",
            description="List conversations for a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"},
                    "limit": {"type": "integer", "description": "Number of results (max 100)", "default": 20},
                    "skip": {"type": "integer", "description": "Number of results to skip", "default": 0}
                }
            }
        ),
        Tool(
            name="ghl_conversations_get",
            description="Get details of a specific conversation",
            inputSchema={
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "string", "description": "Conversation ID"}
                },
                "required": ["conversation_id"]
            }
        ),
        Tool(
            name="ghl_conversations_create",
            description="Create a new conversation with a contact",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"},
                    "contact_id": {"type": "string", "description": "Contact ID"}
                },
                "required": ["contact_id"]
            }
        ),
        Tool(
            name="ghl_conversations_search",
            description="Search conversations by query",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"},
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="ghl_messages_list",
            description="Get messages in a conversation",
            inputSchema={
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "string", "description": "Conversation ID"},
                    "limit": {"type": "integer", "description": "Number of messages", "default": 20}
                },
                "required": ["conversation_id"]
            }
        ),
        Tool(
            name="ghl_messages_send_sms",
            description="Send an SMS message to a contact",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"},
                    "message": {"type": "string", "description": "Message content"}
                },
                "required": ["contact_id", "message"]
            }
        ),
        Tool(
            name="ghl_messages_send_email",
            description="Send an email to a contact",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"},
                    "subject": {"type": "string", "description": "Email subject"},
                    "message": {"type": "string", "description": "Email body (HTML supported)"},
                    "from_email": {"type": "string", "description": "From email address"}
                },
                "required": ["contact_id", "subject", "message"]
            }
        ),
        Tool(
            name="ghl_messages_send_whatsapp",
            description="Send a WhatsApp message to a contact",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"},
                    "message": {"type": "string", "description": "Message content"}
                },
                "required": ["contact_id", "message"]
            }
        ),

        # Calendars/Appointments (10 tools)
        Tool(
            name="ghl_calendars_list",
            description="List all calendars for a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"}
                }
            }
        ),
        Tool(
            name="ghl_calendars_get",
            description="Get calendar details by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string", "description": "Calendar ID"}
                },
                "required": ["calendar_id"]
            }
        ),
        Tool(
            name="ghl_calendars_create",
            description="Create a new calendar",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"},
                    "name": {"type": "string", "description": "Calendar name"},
                    "description": {"type": "string", "description": "Calendar description"},
                    "slot_duration": {"type": "integer", "description": "Slot duration in minutes", "default": 30}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="ghl_calendars_update",
            description="Update an existing calendar",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string", "description": "Calendar ID"},
                    "name": {"type": "string", "description": "Calendar name"},
                    "description": {"type": "string", "description": "Calendar description"}
                },
                "required": ["calendar_id"]
            }
        ),
        Tool(
            name="ghl_calendars_delete",
            description="Delete a calendar",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string", "description": "Calendar ID"}
                },
                "required": ["calendar_id"]
            }
        ),
        Tool(
            name="ghl_calendars_get_free_slots",
            description="Get available time slots for a calendar",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string", "description": "Calendar ID"},
                    "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                    "timezone": {"type": "string", "description": "Timezone (e.g., America/New_York)"}
                },
                "required": ["calendar_id", "start_date", "end_date"]
            }
        ),
        Tool(
            name="ghl_appointments_list",
            description="List appointments for a location or calendar",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"},
                    "calendar_id": {"type": "string", "description": "Filter by calendar ID"},
                    "start_date": {"type": "string", "description": "Start date filter (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "description": "End date filter (YYYY-MM-DD)"}
                }
            }
        ),
        Tool(
            name="ghl_appointments_get",
            description="Get appointment details by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string", "description": "Appointment ID"}
                },
                "required": ["appointment_id"]
            }
        ),
        Tool(
            name="ghl_appointments_create",
            description="Book a new appointment",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string", "description": "Calendar ID"},
                    "contact_id": {"type": "string", "description": "Contact ID"},
                    "start_time": {"type": "string", "description": "Start time (ISO 8601 format)"},
                    "end_time": {"type": "string", "description": "End time (ISO 8601 format)"},
                    "title": {"type": "string", "description": "Appointment title"},
                    "notes": {"type": "string", "description": "Appointment notes"}
                },
                "required": ["calendar_id", "contact_id", "start_time", "end_time"]
            }
        ),
        Tool(
            name="ghl_appointments_update",
            description="Update or cancel an appointment",
            inputSchema={
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string", "description": "Appointment ID"},
                    "start_time": {"type": "string", "description": "New start time (ISO 8601 format)"},
                    "end_time": {"type": "string", "description": "New end time (ISO 8601 format)"},
                    "title": {"type": "string", "description": "Appointment title"},
                    "notes": {"type": "string", "description": "Appointment notes"},
                    "status": {"type": "string", "description": "Status (confirmed, cancelled)"}
                },
                "required": ["appointment_id"]
            }
        ),

        # Pipelines/Opportunities (10 tools)
        Tool(
            name="ghl_pipelines_list",
            description="List all pipelines for a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"}
                }
            }
        ),
        Tool(
            name="ghl_pipelines_get",
            description="Get pipeline details including stages",
            inputSchema={
                "type": "object",
                "properties": {
                    "pipeline_id": {"type": "string", "description": "Pipeline ID"}
                },
                "required": ["pipeline_id"]
            }
        ),
        Tool(
            name="ghl_opportunities_list",
            description="List opportunities with optional filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"},
                    "pipeline_id": {"type": "string", "description": "Filter by pipeline ID"},
                    "stage_id": {"type": "string", "description": "Filter by stage ID"},
                    "status": {"type": "string", "description": "Filter by status (open, won, lost, abandoned)"},
                    "limit": {"type": "integer", "description": "Number of results (max 100)", "default": 20},
                    "skip": {"type": "integer", "description": "Number of results to skip", "default": 0}
                }
            }
        ),
        Tool(
            name="ghl_opportunities_get",
            description="Get opportunity details by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "opportunity_id": {"type": "string", "description": "Opportunity ID"}
                },
                "required": ["opportunity_id"]
            }
        ),
        Tool(
            name="ghl_opportunities_create",
            description="Create a new opportunity",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"},
                    "pipeline_id": {"type": "string", "description": "Pipeline ID"},
                    "stage_id": {"type": "string", "description": "Stage ID"},
                    "contact_id": {"type": "string", "description": "Contact ID"},
                    "name": {"type": "string", "description": "Opportunity name"},
                    "monetary_value": {"type": "number", "description": "Deal value"},
                    "status": {"type": "string", "description": "Status (open, won, lost, abandoned)", "default": "open"}
                },
                "required": ["pipeline_id", "stage_id", "name"]
            }
        ),
        Tool(
            name="ghl_opportunities_update",
            description="Update an existing opportunity",
            inputSchema={
                "type": "object",
                "properties": {
                    "opportunity_id": {"type": "string", "description": "Opportunity ID"},
                    "name": {"type": "string", "description": "Opportunity name"},
                    "monetary_value": {"type": "number", "description": "Deal value"},
                    "status": {"type": "string", "description": "Status (open, won, lost, abandoned)"}
                },
                "required": ["opportunity_id"]
            }
        ),
        Tool(
            name="ghl_opportunities_delete",
            description="Delete an opportunity",
            inputSchema={
                "type": "object",
                "properties": {
                    "opportunity_id": {"type": "string", "description": "Opportunity ID"}
                },
                "required": ["opportunity_id"]
            }
        ),
        Tool(
            name="ghl_opportunities_move_stage",
            description="Move opportunity to a different pipeline stage",
            inputSchema={
                "type": "object",
                "properties": {
                    "opportunity_id": {"type": "string", "description": "Opportunity ID"},
                    "stage_id": {"type": "string", "description": "New stage ID"}
                },
                "required": ["opportunity_id", "stage_id"]
            }
        ),
        Tool(
            name="ghl_opportunities_update_status",
            description="Update opportunity status (won/lost/open/abandoned)",
            inputSchema={
                "type": "object",
                "properties": {
                    "opportunity_id": {"type": "string", "description": "Opportunity ID"},
                    "status": {"type": "string", "description": "Status (open, won, lost, abandoned)"}
                },
                "required": ["opportunity_id", "status"]
            }
        ),
        Tool(
            name="ghl_opportunities_search",
            description="Search opportunities by query",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"},
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        ),

        # Utility (6 tools)
        Tool(
            name="ghl_locations_get",
            description="Get location details and settings",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"}
                }
            }
        ),
        Tool(
            name="ghl_users_list",
            description="List all users in a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"}
                }
            }
        ),
        Tool(
            name="ghl_tags_list",
            description="List all tags for a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"}
                }
            }
        ),
        Tool(
            name="ghl_custom_fields_list",
            description="List custom fields for contacts",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"}
                }
            }
        ),
        Tool(
            name="ghl_workflows_list",
            description="List all workflows for a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"}
                }
            }
        ),
        Tool(
            name="ghl_forms_list",
            description="List all forms for a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Location ID (defaults to GHL_LOCATION_ID env var)"}
                }
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls"""

    # Helper to get location_id
    def get_location_id(args):
        return args.get("location_id", GHL_LOCATION_ID)

    # Format response
    def format_response(data: dict) -> str:
        if "error" in data:
            return f"Error: {data['error']}\n{data.get('details', '')}"
        return json.dumps(data, indent=2)

    try:
        # CONTACTS TOOLS
        if name == "ghl_contacts_list":
            location_id = get_location_id(arguments)
            params = {
                "locationId": location_id,
                "limit": arguments.get("limit", 20),
                "skip": arguments.get("skip", 0)
            }
            if "query" in arguments:
                params["query"] = arguments["query"]
            if "tags" in arguments:
                params["tags"] = arguments["tags"]

            result = await ghl_request("GET", "/contacts", params=params)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_contacts_get":
            contact_id = arguments["contact_id"]
            result = await ghl_request("GET", f"/contacts/{contact_id}")
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_contacts_create":
            location_id = get_location_id(arguments)
            data = {k: v for k, v in arguments.items() if k != "location_id"}
            data["locationId"] = location_id
            result = await ghl_request("POST", "/contacts", json_data=data)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_contacts_update":
            contact_id = arguments.pop("contact_id")
            result = await ghl_request("PUT", f"/contacts/{contact_id}", json_data=arguments)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_contacts_delete":
            contact_id = arguments["contact_id"]
            result = await ghl_request("DELETE", f"/contacts/{contact_id}")
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_contacts_upsert":
            location_id = get_location_id(arguments)
            data = {k: v for k, v in arguments.items() if k != "location_id"}
            data["locationId"] = location_id
            result = await ghl_request("POST", "/contacts/upsert", json_data=data)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_contacts_add_tags":
            contact_id = arguments["contact_id"]
            tags = arguments["tags"]
            result = await ghl_request("POST", f"/contacts/{contact_id}/tags", json_data={"tags": tags})
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_contacts_remove_tags":
            contact_id = arguments["contact_id"]
            tags = arguments["tags"]
            result = await ghl_request("DELETE", f"/contacts/{contact_id}/tags", json_data={"tags": tags})
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_contacts_add_note":
            contact_id = arguments["contact_id"]
            body = arguments["body"]
            result = await ghl_request("POST", f"/contacts/{contact_id}/notes", json_data={"body": body})
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_contacts_get_notes":
            contact_id = arguments["contact_id"]
            result = await ghl_request("GET", f"/contacts/{contact_id}/notes")
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_contacts_add_task":
            contact_id = arguments["contact_id"]
            data = {k: v for k, v in arguments.items() if k != "contact_id"}
            result = await ghl_request("POST", f"/contacts/{contact_id}/tasks", json_data=data)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_contacts_get_tasks":
            contact_id = arguments["contact_id"]
            result = await ghl_request("GET", f"/contacts/{contact_id}/tasks")
            return [TextContent(type="text", text=format_response(result))]

        # CONVERSATIONS/MESSAGING TOOLS
        elif name == "ghl_conversations_list":
            location_id = get_location_id(arguments)
            params = {
                "locationId": location_id,
                "limit": arguments.get("limit", 20),
                "skip": arguments.get("skip", 0)
            }
            result = await ghl_request("GET", "/conversations", params=params)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_conversations_get":
            conversation_id = arguments["conversation_id"]
            result = await ghl_request("GET", f"/conversations/{conversation_id}")
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_conversations_create":
            location_id = get_location_id(arguments)
            contact_id = arguments["contact_id"]
            data = {"locationId": location_id, "contactId": contact_id}
            result = await ghl_request("POST", "/conversations", json_data=data)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_conversations_search":
            location_id = get_location_id(arguments)
            query = arguments["query"]
            params = {"locationId": location_id, "query": query}
            result = await ghl_request("GET", "/conversations/search", params=params)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_messages_list":
            conversation_id = arguments["conversation_id"]
            limit = arguments.get("limit", 20)
            params = {"limit": limit}
            result = await ghl_request("GET", f"/conversations/{conversation_id}/messages", params=params)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_messages_send_sms":
            contact_id = arguments["contact_id"]
            message = arguments["message"]
            data = {"type": "SMS", "contactId": contact_id, "message": message}
            result = await ghl_request("POST", "/conversations/messages", json_data=data)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_messages_send_email":
            contact_id = arguments["contact_id"]
            subject = arguments["subject"]
            message = arguments["message"]
            from_email = arguments.get("from_email")
            data = {
                "type": "Email",
                "contactId": contact_id,
                "subject": subject,
                "message": message
            }
            if from_email:
                data["from"] = from_email
            result = await ghl_request("POST", "/conversations/messages", json_data=data)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_messages_send_whatsapp":
            contact_id = arguments["contact_id"]
            message = arguments["message"]
            data = {"type": "WhatsApp", "contactId": contact_id, "message": message}
            result = await ghl_request("POST", "/conversations/messages", json_data=data)
            return [TextContent(type="text", text=format_response(result))]

        # CALENDARS/APPOINTMENTS TOOLS
        elif name == "ghl_calendars_list":
            location_id = get_location_id(arguments)
            params = {"locationId": location_id}
            result = await ghl_request("GET", "/calendars", params=params)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_calendars_get":
            calendar_id = arguments["calendar_id"]
            result = await ghl_request("GET", f"/calendars/{calendar_id}")
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_calendars_create":
            location_id = get_location_id(arguments)
            data = {k: v for k, v in arguments.items() if k != "location_id"}
            data["locationId"] = location_id
            result = await ghl_request("POST", "/calendars", json_data=data)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_calendars_update":
            calendar_id = arguments.pop("calendar_id")
            result = await ghl_request("PUT", f"/calendars/{calendar_id}", json_data=arguments)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_calendars_delete":
            calendar_id = arguments["calendar_id"]
            result = await ghl_request("DELETE", f"/calendars/{calendar_id}")
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_calendars_get_free_slots":
            calendar_id = arguments["calendar_id"]
            params = {
                "startDate": arguments["start_date"],
                "endDate": arguments["end_date"]
            }
            if "timezone" in arguments:
                params["timezone"] = arguments["timezone"]
            result = await ghl_request("GET", f"/calendars/{calendar_id}/free-slots", params=params)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_appointments_list":
            location_id = get_location_id(arguments)
            params = {"locationId": location_id}
            if "calendar_id" in arguments:
                params["calendarId"] = arguments["calendar_id"]
            if "start_date" in arguments:
                params["startDate"] = arguments["start_date"]
            if "end_date" in arguments:
                params["endDate"] = arguments["end_date"]
            result = await ghl_request("GET", "/appointments", params=params)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_appointments_get":
            appointment_id = arguments["appointment_id"]
            result = await ghl_request("GET", f"/appointments/{appointment_id}")
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_appointments_create":
            data = arguments.copy()
            result = await ghl_request("POST", "/appointments", json_data=data)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_appointments_update":
            appointment_id = arguments.pop("appointment_id")
            result = await ghl_request("PUT", f"/appointments/{appointment_id}", json_data=arguments)
            return [TextContent(type="text", text=format_response(result))]

        # PIPELINES/OPPORTUNITIES TOOLS
        elif name == "ghl_pipelines_list":
            location_id = get_location_id(arguments)
            params = {"locationId": location_id}
            result = await ghl_request("GET", "/opportunities/pipelines", params=params)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_pipelines_get":
            pipeline_id = arguments["pipeline_id"]
            result = await ghl_request("GET", f"/opportunities/pipelines/{pipeline_id}")
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_opportunities_list":
            location_id = get_location_id(arguments)
            params = {
                "locationId": location_id,
                "limit": arguments.get("limit", 20),
                "skip": arguments.get("skip", 0)
            }
            if "pipeline_id" in arguments:
                params["pipelineId"] = arguments["pipeline_id"]
            if "stage_id" in arguments:
                params["stageId"] = arguments["stage_id"]
            if "status" in arguments:
                params["status"] = arguments["status"]
            result = await ghl_request("GET", "/opportunities", params=params)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_opportunities_get":
            opportunity_id = arguments["opportunity_id"]
            result = await ghl_request("GET", f"/opportunities/{opportunity_id}")
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_opportunities_create":
            location_id = get_location_id(arguments)
            data = {k: v for k, v in arguments.items() if k != "location_id"}
            data["locationId"] = location_id
            result = await ghl_request("POST", "/opportunities", json_data=data)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_opportunities_update":
            opportunity_id = arguments.pop("opportunity_id")
            result = await ghl_request("PUT", f"/opportunities/{opportunity_id}", json_data=arguments)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_opportunities_delete":
            opportunity_id = arguments["opportunity_id"]
            result = await ghl_request("DELETE", f"/opportunities/{opportunity_id}")
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_opportunities_move_stage":
            opportunity_id = arguments["opportunity_id"]
            stage_id = arguments["stage_id"]
            result = await ghl_request("PUT", f"/opportunities/{opportunity_id}", json_data={"stageId": stage_id})
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_opportunities_update_status":
            opportunity_id = arguments["opportunity_id"]
            status = arguments["status"]
            result = await ghl_request("PUT", f"/opportunities/{opportunity_id}", json_data={"status": status})
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_opportunities_search":
            location_id = get_location_id(arguments)
            query = arguments["query"]
            params = {"locationId": location_id, "query": query}
            result = await ghl_request("GET", "/opportunities/search", params=params)
            return [TextContent(type="text", text=format_response(result))]

        # UTILITY TOOLS
        elif name == "ghl_locations_get":
            location_id = get_location_id(arguments)
            result = await ghl_request("GET", f"/locations/{location_id}")
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_users_list":
            location_id = get_location_id(arguments)
            params = {"locationId": location_id}
            result = await ghl_request("GET", "/users", params=params)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_tags_list":
            location_id = get_location_id(arguments)
            params = {"locationId": location_id}
            result = await ghl_request("GET", "/tags", params=params)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_custom_fields_list":
            location_id = get_location_id(arguments)
            params = {"locationId": location_id}
            result = await ghl_request("GET", "/custom-fields", params=params)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_workflows_list":
            location_id = get_location_id(arguments)
            params = {"locationId": location_id}
            result = await ghl_request("GET", "/workflows", params=params)
            return [TextContent(type="text", text=format_response(result))]

        elif name == "ghl_forms_list":
            location_id = get_location_id(arguments)
            params = {"locationId": location_id}
            result = await ghl_request("GET", "/forms", params=params)
            return [TextContent(type="text", text=format_response(result))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except RateLimitError as e:
        return [TextContent(type="text", text=f"Rate Limit Error: {str(e)}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
