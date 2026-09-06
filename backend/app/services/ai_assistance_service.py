import os
from dotenv import load_dotenv
from openai import OpenAI
from backend.app.services.scheduler_service import schedule
import json


VPN_PORT = "7897"
os.environ["http_proxy"] = f"http://127.0.0.1:{VPN_PORT}"
os.environ["https_proxy"] = f"http://127.0.0.1:{VPN_PORT}"
os.environ["HTTP_PROXY"] = f"http://127.0.0.1:{VPN_PORT}"
os.environ["HTTPS_PROXY"] = f"http://127.0.0.1:{VPN_PORT}"

_client = None
def getAIClient():
    global _client
    if _client is None:
        load_dotenv("backend/.env")
        API_KEY  = os.getenv("AI_API_KEY")
        if API_KEY:
            _client = OpenAI(api_key = API_KEY)
    
    if _client is None:
        raise RuntimeError("AI_API_KEY is not configured")
    return _client


def _response_payload(response):
    parsed = getattr(response, "output_parsed", None)
    if parsed is not None:
        return parsed.model_dump() if hasattr(parsed, "model_dump") else parsed
    return json.loads(response.output_text)


def _task_dict(task):
    if hasattr(task, "model_dump"):
        return task.model_dump()
    return dict(task)


def _task_list(structured_tasks):
    if isinstance(structured_tasks, dict):
        structured_tasks = structured_tasks.get("sub_tasks", [])
    return [_task_dict(task) for task in structured_tasks]
#More structured layers of ai assistant workflow: input user prompt
#STATE 1: Validate
#STATE 2: Clarify
#STATE 3: Confirm
#STATE 4: Schedule
#Validation Layer Loop

#1. Clarification Layer loop
#Input the user prompt to LLM, determine if the task description is clear or not
#What defines a task description is clear or not:
#Do we know the input? Do we know the output? What tools we can use?
#If not clear, go back to the first step of the layer, ask for clarification questions
#If clear, then move to next layer

#2. LLM decomposition Layer
#Input tasks and clarification to LLM
#LLM breaks down the task to subtasks with reasons and a final deadline

#3. LLM structuring layer
#Input the output from last layer
#strict out the unit of duration, format of deadline and schema with several ruls
#output structured json

#4. Confirmation Layer loop (Later)
#Display the determined task list to user
#If the user says yes, then schedule those tasks
#If the user feels no, then asks for improvement

#TODO: Decide whether to combine layer 2 and 3
#Cons of combine: Low cost (only one LLM call), Fast, simpler architecture
#Pros of combine: More accurate output (LLM does better job when focusing), Easier



def ai_assistance_control_center(messages):
    if not messages:
        return {"status": "error", "message": "No conversation provided"}
    latest_user_message = messages[len(messages)-1]
    if(latest_user_message.role != "user"):
        return {"status": "error", "message": "last message is not from the user"}
    
    # clarification_result = {
    #     status: "need_clarify" or "no_need_clarify"
    #     clarified_task: "task description"
    #     known_info:
    #     {
    #         constraint: ,,,,
    #         content: ,,,,
    #     },
    #     missing_info:[deadline],
    #     questions_set: [questions]
    # }

    clarification_result = _clarification_layer(
        messages = messages,
        latest_user_message = latest_user_message
    )
    if clarification_result["status"] == "clear":
        clarification_result = clarification_result
    else:
        return clarification_result
    
    #Enter decomposition state
    decomposed_task = _decomposition_layer(
        clarification_result = clarification_result,
        messages = messages
    )

    structured_tasks = _structuring_layer(
        decomposed_task = decomposed_task
    )

    return structured_tasks
    #enter decomposition stage
def _clarification_layer(messages, latest_user_message):
    client = getAIClient()
    response = client.responses.create(
        model="gpt-5.5",  # define the model to use
        reasoning={"effort": "low"},
        instructions=(
            "You are the clarification layer for a task-planning system. "

            "The task is considered sufficiently clear when the following required sections can be determined well enough to create a useful plan: "

            "1. deliverable: the concrete goal or result the user wants to complete. "
            "2. deadline: the time by which the deliverable should be completed, or a usable time target if no strict deadline exists. "
            "3. estimated_duration: a reasonable planning estimate of the amount of time needed to complete the deliverable. "
            "The estimate does not need to be precise. It only needs to be reasonable enough for scheduling. "
            "4. constraints: additional information that materially affects the deliverable, deadline, or estimated_duration. "
            "Constraints are not an independent category of miscellaneous details. "
            "They are dependencies of the other required sections. "
            "Examples include task scope, location, industry, required format, available resources, travel distance, "
            "task dependencies, or other information that significantly changes what must be done, when it must be done, "
            "or how long it is likely to take. "

            "Evaluate the required sections in this order: deliverable, deadline, estimated_duration, then constraints. "

            "For each required section, request clarification only when either of the following is true: "
            "1. the section cannot be inferred from the conversation with enough confidence to support a useful plan; "
            "2. missing information would materially change the deliverable, make the deadline unusable, "
            "or make a reasonable duration estimate impossible. "

            "Do not require the user to fully specify the task scope. "
            "Real-world task requests are often incomplete. "
            "If the user's description provides a recognizable task type and a reasonably bounded scope, "
            "use typical assumptions for comparable tasks and proceed. "

            "Missing details that affect only the precision of the duration estimate should not trigger clarification. "
            "For example, uncertainty between roughly 2 and 4 hours is normally acceptable for planning. "
            "Clarification is appropriate when the missing information could change the task from one substantially different scale to another, "
            "such as from a short task to a multi-day task, or when the actual work cannot be identified at all. "

            "When a required section depends on additional information, first determine whether that information can be reasonably inferred "
            "from the task type, normal conventions, or the rest of the conversation. "
            "Ask for clarification only if it cannot be reasonably inferred and the uncertainty materially prevents planning. "

            "Do not ask the user to provide an estimated duration when the system can estimate it from typical comparable tasks. "
            "Duration estimation is the responsibility of the planning system when sufficient task context exists. "

            "When estimating duration, use the following process: "

            "1. Consider several normal and plausible conditions under which the task could be completed, "
            "using only the information and constraints already provided by the user. "

            "2. Estimate three values: "
            "- lower_bound: a relatively fast but realistic completion time; "
            "- typical_time: the most likely completion time; "
            "- upper_bound: a relatively slow but still normal completion time. "
            "Do not include rare extreme cases. "

            "3. Measure the uncertainty using the plausible duration range: "
            "duration_range = upper_bound - lower_bound. "

            "Also compare the range to the typical duration using: "
            "relative_range = duration_range / typical_time. "

            "4. Treat the completion time as sufficiently concentrated when BOTH are true: "
            "- duration_range is no more than 60 minutes; "
            "- relative_range is no more than 50 percent. "

            "If either threshold is exceeded, the duration is too uncertain for reliable planning. "
            "Identify which missing condition causes the variation and request clarification about that condition. "

            "5. If the duration is sufficiently concentrated, do not ask for clarification. "
            "Use the upper_bound as the estimated duration so the schedule includes a conservative time buffer. "

            "Use the following scope rule: "
            "scope is sufficient when the task category, main deliverable, and approximate amount of work are clear enough "
            "to generate meaningful subtasks and a reasonable duration estimate. "
            "Exact item counts, detailed specifications, current progress, data readiness, or preferred implementation choices "
            "are not required unless they would fundamentally change the workload or deliverable. "

            "Example: the user says, 'Finish my topology homework by next Tuesday, chapter 7 exercises.' "
            "The deliverable is clear, the deadline is usable, and 'chapter 7 exercises' provides a reasonably bounded scope. "
            "Even though the exact exercise numbers and current progress are unknown, these details usually affect only the precision of the estimate. "
            "Estimate the duration using a typical chapter-level homework workload and do not clarify. "

            "Example: the user says, 'Pack up my apartment for move-out by August 25.'"
            "The deliverable is clear, and the deadline is clear, however, if we follow the thinking process of estimating duration time"
            "Firstly, the user may pack his/her 1b1b apartment, or a house, or 3b3b apartment. The areas affect the time"
            "For apartment size, packing time may exponentially change. For example, it make take 2 hours for 1b1b, but 5 hours for 3b3b"
            "So, it exceed the threshold, you should propose a clarification question about this condition."
            "In practice, I want you to be more accurate about getting the time under conditions, either searching online or experiences"

            "You must fill every output property according to its purpose: "
            "'status' must be either 'clear' or 'needs_clarification'; "
            "'clarified_task' must be a concise restatement of the user's actual goal; "
            "'known_info' must contain the currently inferred deliverable, deadline, estimated_duration, and constraints; "
            "'missing_info' must list only information that still prevents a useful inference of a required section; "
            "'questions' must contain the minimum concrete follow-up questions needed to resolve missing_info. "

            "If all required sections can be inferred well enough for useful planning, set status to 'clear' "
            "and set missing_info and questions to empty arrays. "
            "Do not invent user-specific facts that are not supported by the conversation, "
            "but reasonable generic assumptions about typical task execution are allowed for planning."
        ),
        input=[
            {
                "role": "developer",
                "content": (
                    "Evaluate the conversation history. "
                    "Decide whether clarification is needed before task decomposition. "
                    "If needed, ask the minimum set of concrete follow-up questions."
                )
            },
            *[
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
        ],
        text={
            "format": {
                "type": "json_schema",
                "strict": True,
                "name": "clarification_result",
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["clear", "needs_clarification"]
                        },
                        "clarified_task": {
                            "type": "string"
                        },
                        "known_info": {
                            "type": "object",
                            "properties": {
                                "deliverable": {
                                    "type": ["string", "null"]
                                },
                                "estimated_duration_minutes":{
                                    "type": ["integer", "null"]
                                },
                                "deadline": {
                                    "type": ["string", "null"]
                                },
                                "constraints": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                            },
                            "required": [
                                "deliverable",
                                "deadline",
                                "constraints",
                                "estimated_duration_minutes"
                            ],
                            "additionalProperties": False
                        },
                        "missing_info": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "questions": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": [
                        "status",
                        "clarified_task",
                        "known_info",
                        "missing_info",
                        "questions"
                    ],
                    "additionalProperties": False
                }
            }
        }
    )
    return _response_payload(response)

def _decomposition_layer(clarification_result, messages):
    clarified_task = clarification_result["clarified_task"]
    known_info = clarification_result["known_info"]
    client = getAIClient()

    developer_content = "\n".join([
    "The following information has already been clarified through previous conversations with the user:",
    f"Final goal: {clarified_task}",
    f"Deliverable: {known_info.get('deliverable', '')}",
    f"Deadline: {known_info.get('deadline', '')}",
    f"Constraints: {', '.join(known_info.get('constraints', []))}",
    f"Tools needed: {', '.join(known_info.get('tools_needed', []))}"
    ])

    response = client.responses.create(
        model="gpt-5.6",
        reasoning={"effort": "high"},
        instructions=(
            "You are the decomposition layer for task planning. "
            "Break the clarified task into a small set of concrete, actionable sub_tasks needed to complete the final deliverable. "
            "Each sub_task must represent one meaningful step, not a vague goal and not an overly tiny action. "
            "For each sub_task, provide: "
            "1. deliverable: the specific output or result of that step, "
            "2. deadline: when that step should be finished, consistent with the final deadline, "
            "3. estimated_duration: approximately how long will need to finish the task in minutes"
            "4. reason: why this step is necessary. "
            "Use known_info and the conversation history carefully. "
            "Do not invent missing critical facts. "
            "Make the plan complete, ordered, non-duplicative, and feasible within the user's constraints."
        ),
        input = (
            {
                "role" : "developer",
                "content":developer_content
            },
            {
                "role": "developer",
                "content":"The following is the conversation history between the AI agent and the user for your references"
            },
            *[
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
        ),
        text = {
            "format": {
                "type": "json_schema",
                "strict": True,
                "name": "decomposition_result",
                "schema":{
                        "type": "object",
                        "properties": {
                            "status":{
                                "type": "string",
                                "enum": ["decomposed"]
                            },
                            "sub_tasks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                "deliverable": { "type": "string" },
                                "estimated_duration_minutes": {
                                        "type": ["integer", "null"]
                                },
                                "deadline": { "type": "string" },
                                "reason": { "type": "string" }
                                },
                                "required": ["deliverable", "estimated_duration_minutes", "deadline", "reason"],
                                "additionalProperties": False
                            }
                            }
                        },
                        "required": ["status", "sub_tasks"],
                        "additionalProperties": False
                    }
            }
        }
    )
    return _response_payload(response)
def _structuring_layer(decomposed_task):
    decomposition_result = decomposed_task
    sub_tasks = decomposition_result.get("sub_tasks", [])
    client = getAIClient()
    response = client.responses.create(
        model="gpt-5.5",
        reasoning={"effort": "low"},
        instructions=(
            "You are the structuring layer for task planning. "
            "Convert the decomposed task list into a normalized structured format for downstream scheduling. "
            "You must fill every output property according to its purpose: "
            "'sub_tasks' must be an ordered array; "
            "'title' must be a concise task name; "
            "'deadline' must be the sub-task deadline as a string, preserving known timing information without inventing new facts; "
            "'estimated_duration_minutes' must be an integer number of minutes if it can be reasonably inferred, otherwise null; "
            "'reason' must explain why the sub-task is needed; "
            "'depends_on' must list the titles of earlier sub-tasks that must be completed first. "
            "Keep the plan feasible, non-duplicative, and consistent with the decomposition input. "
            "Do not guess critical missing facts."
        ),
        input=[
            {
                "role": "developer",
                "content": (
                    "Normalize the following decomposed sub-tasks into a strict scheduling schema. "
                    "Preserve order unless a dependency requires otherwise."
                )
            },
            {
                "role": "developer",
                "content": str(sub_tasks)
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "strict": True,
                "name": "structuring_result",
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["success"]
                        },
                        "sub_tasks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "deadline": {"type": "string"},
                                    "estimated_duration_minutes": {
                                        "type": ["integer", "null"]
                                    },
                                    "reason": {"type": "string"},
                                    "depends_on": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    }
                                },
                                "required": [
                                    "title",
                                    "deadline",
                                    "estimated_duration_minutes",
                                    "reason",
                                    "depends_on"
                                ],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["status", "sub_tasks"],
                    "additionalProperties": False
                }
            }
        }
    )
    return _response_payload(response)

def handle_task_confirmation(cred, decision, messages, structured_tasks, feedback):
    if(decision == "yes"):
        return handle_task_schedule(cred, structured_tasks)
    
    if(decision == "no"):
        return handle_feedback_improvement(messages, structured_tasks, feedback)

    return {"status": "error", "message": "Invalid decision"}    

def handle_task_schedule(cred, structured_tasks):
    scheduler_ready_tasks = [
        {
            "title": task["title"],
            "estimated_duration": (task.get("estimated_duration_minutes") or 60) / 60,
            "deadline": task["deadline"],
            "priority": task.get("priority", "medium"),
            "depends_on": task.get("depends_on", []),
        }
        for task in _task_list(structured_tasks)
    ]
    schedule_result = schedule(cred, scheduler_ready_tasks)
    return {
        "status": "scheduled",
        "schedule": schedule_result,
    }

def handle_feedback_improvement(messages, structured_tasks, feedbacks):
    if not feedbacks:
        return {"status": "error", "message": "Feedback is required for task improvement"}

    current_sub_tasks = _task_list(structured_tasks)
    client = getAIClient()
    response = client.responses.create(
        model="gpt-5.5",
        reasoning={"effort": "low"},
        instructions=(
            "You are given a conversation history, the current structured task plan, and user feedback. "
            "Revise the current plan according to the feedback while preserving the original intent unless the user clearly changed it. "
            "Use the conversation history only as supporting context when the feedback is ambiguous. "
            "Return an improved version of the structured task plan using the exact schema requested."
        ),
        input=[
            {
                "role": "developer",
                "content": (
                    "The following tasks are the current structured task plan that needs improvement."
                )
            },
            {
                "role": "developer",
                "content": str(current_sub_tasks)
            },
            {
                "role": "developer",
                "content": "The following messages contain the user's feedback on the current plan."
            },
            *[
                {"role": feedback.role, "content": feedback.content}
                for feedback in feedbacks
            ],
            {
                "role": "developer",
                "content": "The following information is about the conversation history for your reference"
            },
            *[
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
        ],
        text={
            "format": {
                "type": "json_schema",
                "strict": True,
                "name": "improved_tasks",
                "schema": {
                    "type": "object",
                    "properties": {
                        "status":{
                            "type": "string",
                            "enum": ["waiting_feedback"]
                        },
                        "sub_tasks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "deadline": {"type": "string"},
                                    "estimated_duration_minutes": {
                                        "type": ["integer", "null"]
                                    },
                                    "reason": {"type": "string"},
                                    "depends_on": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    }
                                },
                                "required": [
                                    "title",
                                    "deadline",
                                    "estimated_duration_minutes",
                                    "reason",
                                    "depends_on"
                                ],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["status", "sub_tasks"],
                    "additionalProperties": False
                }
            }
        }
    )
    return _response_payload(response)

