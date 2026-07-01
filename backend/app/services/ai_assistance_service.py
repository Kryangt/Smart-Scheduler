import os
from dotenv import load_dotenv
from openai import OpenAI
from backend.app.services.scheduler_service import schedule


_client = None
def getAIClient():

    if _client is None:
        load_dotenv("backend/.env")
        API_KEY  = os.getenv("AI_API_KEY")
        if not API_KEY:
            _client = OpenAI(api_key = API_KEY)
    
    return _client
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



def ai_assistance_control_center(user_input):
    messages = user_input.messages

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
            "You are the clarification layer for task planning. "
            "Review the conversation and decide whether there is enough information to plan the task. "
            "A task is clear only if you can identify the user's intended deliverable, relevant deadline or time target, important constraints, and any required tools or resources. "
            "You must fill every output property according to its purpose: "
            "'status' must be either 'clear' or 'needs_clarification'; "
            "'clarified_task' must be a concise restatement of the user's actual goal; "
            "'known_info' must contain the information already provided in the conversation; "
            "'missing_info' must list only the critical information that is still missing; "
            "'questions' must contain the minimum concrete follow-up questions needed to get the missing information. "
            "If the task is already clear, set 'missing_info' and 'questions' to empty arrays. "
            "Do not guess missing critical facts, and do not ask unnecessary questions."
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
                                "deadline": {
                                    "type": ["string", "null"]
                                },
                                "constraints": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "tools_needed": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            },
                            "required": [
                                "deliverable",
                                "deadline",
                                "constraints",
                                "tools_needed"
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
    return response.output_parsed

def _decomposition_layer(clarification_result, messages):
    clarified_task = clarification_result["clarified_task"]
    known_info = clarification_result["known_info"]
    client = getAIClient()
    response = client.responses.create(
        model = "gpt-5.3-chat-latest",
        reasoning= {"effort": "high"},
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
                "content":[
                    "The following information has already been clarified through previous conversations with the user:",
                    "Final goal" + clarified_task,
                    *[
                        string
                        for string in known_info
                    ]
                ]
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
                                "required": ["deliverable", "estimated_duration", "deadline", "reason"],
                                "additionalProperties": False
                            }
                            }
                        },
                        "required": ["sub_tasks"],
                        "additionalProperties": False
                    }
            }
        }
    )
    return response.output_parsed
def _structuring_layer(decomposed_task):

    
    decomposition_result = decomposed_task
    sub_tasks = decomposition_result.get("sub_tasks", [])
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
                    "required": ["sub_tasks"],
                    "additionalProperties": False
                }
            }
        }
    )
    return response.output_parsed

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
            "estimated_duration": task["estimated_duration_minutes"],
            "deadline": task["deadline"]
        }
        for task in structured_tasks.get("sub_tasks", [])
    ]
    schedule(cred, scheduler_ready_tasks)
    return {"status": "finish task decomposition cycle"}

def handle_feedback_improvement(messages, structured_tasks, feedbacks):
    if not feedbacks:
        return {"status": "error", "message": "Feedback is required for task improvement"}

    current_sub_tasks = structured_tasks.get("sub_tasks", [])

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
                    "required": ["sub_tasks"],
                    "additionalProperties": False
                }
            }
        }
    )
    return response.output_parsed

