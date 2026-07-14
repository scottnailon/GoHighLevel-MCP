# GoHighLevel MCP — Tool Reference

**Total tools:** 59 across 13 categories.

Auto-generated from FastMCP registration. Regenerate with `python -m scripts.gen_tools_doc`.

## Index

- [appointments](#appointments) — 4 tools
- [calendars](#calendars) — 6 tools
- [contacts](#contacts) — 12 tools
- [conversations](#conversations) — 4 tools
- [custom](#custom) — 5 tools
- [forms](#forms) — 2 tools
- [funnels](#funnels) — 2 tools
- [messages](#messages) — 4 tools
- [opportunities](#opportunities) — 8 tools
- [pipelines](#pipelines) — 5 tools
- [tags](#tags) — 1 tools
- [users](#users) — 4 tools
- [workflows](#workflows) — 2 tools

---

## appointments

### `ghl_appointments_create`

*Book appointment* · ✏️ mutating

Book an appointment on a calendar for a contact at a specific time.

### `ghl_appointments_get`

*Get appointment* · 🔒 read-only ♻️ idempotent

Get full details of a single appointment.

### `ghl_appointments_list`

*List appointments* · 🔒 read-only ♻️ idempotent

List appointments on a calendar, optionally filtered by contact, user, or date range.

### `ghl_appointments_update`

*Update appointment* · ✏️ mutating ♻️ idempotent

Update or cancel an appointment. Pass appointment_status='cancelled' to cancel.

## calendars

### `ghl_calendars_create`

*Create calendar* · ✏️ mutating

Create a new calendar with bookable slot configuration.

### `ghl_calendars_delete`

*Delete calendar* · ✏️ mutating ⚠️ destructive ♻️ idempotent

Delete a calendar permanently. Existing appointments may also be cancelled.

### `ghl_calendars_get`

*Get calendar* · 🔒 read-only ♻️ idempotent

Get full configuration of a calendar by ID.

### `ghl_calendars_get_free_slots`

*Get available calendar slots* · 🔒 read-only ♻️ idempotent

Get available booking slots for a calendar in the given date range.

### `ghl_calendars_list`

*List calendars* · 🔒 read-only ♻️ idempotent

List all calendars on a location.

### `ghl_calendars_update`

*Update calendar* · ✏️ mutating ♻️ idempotent

Update calendar configuration.

## contacts

### `ghl_contacts_add_note`

*Add note to contact* · ✏️ mutating

Append a note to a contact's record. Useful for logging call outcomes, observations, follow-ups.

### `ghl_contacts_add_tags`

*Add tags to contact* · ✏️ mutating ♻️ idempotent

Add one or more tags to a contact. Idempotent — duplicate tags are ignored by GHL.

### `ghl_contacts_add_task`

*Create task for contact* · ✏️ mutating

Create a task associated with a contact (e.g. "Follow up Tuesday").

### `ghl_contacts_create`

*Create contact* · ✏️ mutating

Create a new contact in a GHL location.

### `ghl_contacts_delete`

*Delete contact* · ✏️ mutating ⚠️ destructive ♻️ idempotent

Delete a contact permanently. This cannot be undone.

### `ghl_contacts_get`

*Get contact* · 🔒 read-only ♻️ idempotent

Get full details for a single contact by ID, including custom field values.

### `ghl_contacts_get_notes`

*List contact notes* · 🔒 read-only ♻️ idempotent

Retrieve all notes attached to a contact, newest first.

### `ghl_contacts_get_tasks`

*List contact tasks* · 🔒 read-only ♻️ idempotent

Retrieve all tasks for a contact (open and completed).

### `ghl_contacts_list`

*List contacts* · 🔒 read-only ♻️ idempotent

List or search contacts in a GHL location.

### `ghl_contacts_remove_tags`

*Remove tags from contact* · ✏️ mutating ⚠️ destructive ♻️ idempotent

Remove one or more tags from a contact.

### `ghl_contacts_update`

*Update contact* · ✏️ mutating ♻️ idempotent

Update fields on an existing contact. Only fields you pass are modified.

### `ghl_contacts_upsert`

*Create or update contact (upsert)* · ✏️ mutating ♻️ idempotent

Create or update a contact, deduplicated by email or phone.

## conversations

### `ghl_conversations_create`

*Create conversation* · ✏️ mutating

Create a new conversation thread for a contact.

### `ghl_conversations_get`

*Get conversation* · 🔒 read-only ♻️ idempotent

Get full details of a single conversation including the message thread metadata.

### `ghl_conversations_list`

*List conversations* · 🔒 read-only ♻️ idempotent

List conversations in a location, optionally filtered by contact or assignee.

### `ghl_conversations_search`

*Search conversations* · 🔒 read-only ♻️ idempotent

Free-text search across conversation messages.

## custom

### `ghl_custom_fields_create`

*Create custom field* · ✏️ mutating

Create a new custom field on a location.

### `ghl_custom_fields_delete`

*Delete custom field* · ✏️ mutating ⚠️ destructive ♻️ idempotent

Delete a custom field permanently. Existing data on contacts/opportunities is also lost.

### `ghl_custom_fields_get`

*Get custom field* · 🔒 read-only ♻️ idempotent

Get full details for a single custom field, including its options for picklist types.

### `ghl_custom_fields_list`

*List custom fields* · 🔒 read-only ♻️ idempotent

List all custom fields configured on a location.

### `ghl_custom_fields_update`

*Update custom field* · ✏️ mutating ♻️ idempotent

Update name, placeholder, position, or picklist options of a custom field.

## forms

### `ghl_forms_get_submissions`

*List form submissions* · 🔒 read-only ♻️ idempotent

List form submissions, optionally filtered by form ID or date range.

### `ghl_forms_list`

*List forms* · 🔒 read-only ♻️ idempotent

List all forms configured on a location.

## funnels

### `ghl_funnels_get_pages`

*List funnel pages* · 🔒 read-only ♻️ idempotent

List all pages within a specific funnel.

### `ghl_funnels_list`

*List funnels* · 🔒 read-only ♻️ idempotent

List all funnels on a location.

## messages

### `ghl_messages_list`

*List messages in conversation* · 🔒 read-only ♻️ idempotent

List messages in a conversation thread.

### `ghl_messages_send_email`

*Send email* · ✏️ mutating

Send a transactional email to a contact. Provide ``html``, ``text``, or both.

### `ghl_messages_send_sms`

*Send SMS* · ✏️ mutating

Send an SMS to a contact. Charges against the location's wallet at standard markup.

### `ghl_messages_send_whatsapp`

*Send WhatsApp message* · ✏️ mutating

Send a WhatsApp message to a contact (requires WhatsApp Business setup on the location).

## opportunities

### `ghl_opportunities_create`

*Create opportunity* · ✏️ mutating

Create a new opportunity. Requires pipeline, stage, name, and a contact ID.

### `ghl_opportunities_delete`

*Delete opportunity* · ✏️ mutating ⚠️ destructive ♻️ idempotent

Delete an opportunity permanently.

### `ghl_opportunities_get`

*Get opportunity* · 🔒 read-only ♻️ idempotent

Get full details for a single opportunity including custom fields.

### `ghl_opportunities_list`

*List opportunities* · 🔒 read-only ♻️ idempotent

List/search opportunities with filtering by pipeline, stage, status, contact, assignee, or free-text query.

### `ghl_opportunities_move_stage`

*Move opportunity to stage* · ✏️ mutating ♻️ idempotent

Move an opportunity to a different pipeline stage. Convenience wrapper around ``ghl_opportunities_update``.

### `ghl_opportunities_search`

*Search opportunities* · 🔒 read-only ♻️ idempotent

Alias of ``ghl_opportunities_list`` with the ``query`` parameter emphasized for free-text search.

### `ghl_opportunities_update`

*Update opportunity* · ✏️ mutating ♻️ idempotent

Update fields on an opportunity. Only fields you pass are modified.

### `ghl_opportunities_update_status`

*Update opportunity status* · ✏️ mutating ♻️ idempotent

Mark an opportunity won, lost, abandoned, or back to open.

## pipelines

### `ghl_pipelines_create`

*Create pipeline* · ✏️ mutating

Create a new sales pipeline with ordered stages.

### `ghl_pipelines_delete`

*Delete pipeline* · ✏️ mutating ⚠️ destructive ♻️ idempotent

Delete a pipeline. All opportunities within it are also deleted. CANNOT BE UNDONE.

### `ghl_pipelines_get`

*Get pipeline details* · 🔒 read-only ♻️ idempotent

Get full details of a single pipeline including all stages.

### `ghl_pipelines_list`

*List pipelines* · 🔒 read-only ♻️ idempotent

List all sales pipelines configured on a location, including their stages.

### `ghl_pipelines_update`

*Update pipeline* · ✏️ mutating ♻️ idempotent

Update a pipeline's name or stages. Replacing ``stages`` replaces ALL stages — be careful with existing opportunities.

## tags

### `ghl_tags_list`

*List tags* · 🔒 read-only ♻️ idempotent

List all tags currently in use on a location.

## users

### `ghl_users_create`

*Create user* · ✏️ mutating

Create a new user on a location.

### `ghl_users_get`

*Get user* · 🔒 read-only ♻️ idempotent

Get full details of a single user.

### `ghl_users_list`

*List users* · 🔒 read-only ♻️ idempotent

List all users with access to a location.

### `ghl_users_update`

*Update user* · ✏️ mutating ♻️ idempotent

Update a user's profile fields.

## workflows

### `ghl_workflows_add_contact`

*Enroll contact in workflow* · ✏️ mutating

Enroll a contact in a workflow, triggering its first step.

### `ghl_workflows_list`

*List workflows* · 🔒 read-only ♻️ idempotent

List all workflows configured on a location.
