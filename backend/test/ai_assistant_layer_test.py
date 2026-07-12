from fastapi.testclient import TestClient
from unittest.mock import patch
from types import SimpleNamespace

from backend.app.main import app, ChatMessage
from backend.app.services.ai_assistance_service import (
    ai_assistance_control_center,
    handle_feedback_improvement,
)

client = TestClient(app)

@patch("backend.app.main.ai_assistance_control_center")
def test_task_decomposition(mock_ai):
    mock_ai.return_value = {
        "status": "clear",
        "sub_tasks": [
            {
                "title": "Research topic",
                "deadline": "2026-07-10",
                "estimated_duration_minutes": 60
            }
        ]
    }

    response = client.post(
        "/task-decomposition",
        json={
            "clarifyMessages": [
                {
                    "id": 1,
                    "role": "user",
                    "content": "Help me finish my research project"
                }
            ]
        }
    )

    print(response.status_code)
    print(response.json())

    assert response.status_code == 200

    data = response.json()

    print(response.status_code)
    print(response.json())

    assert data["status"] == "clear"
    assert data["sub_tasks"][0]["title"] == "Research topic"

    mock_ai.assert_called_once()

def ai_fake_message(data):
    return SimpleNamespace(output_parsed = data)
    
@patch("backend.app.services.ai_assistance_service.getAIClient")
def test_decomposition_workflow(mock_getAIClient):
    mock_ai_client = mock_getAIClient.return_value
    mock_ai_client.responses.create.side_effect = [
        #openAI call 1: the model should return "need_clarification"
        ai_fake_message({
            "status": "needs_clarification",
            "clarified_task": "math homework",
            "known_info": {
                "deliverable": "finish the math homework",
                "deadline": None,
                "constraints": ["only use knowledge from chapter 10"],
                "tools_needed": ["N/A"]
            },
            "missing_info":["deadline"],
            "questions":["when does the homework due?"]
        }),
        #openAI call 2: clear response
        ai_fake_message({
            "status": "clear",
            "clarified_task": "Finish the math homework by July 4, 2026.",
            "known_info": {
                "deliverable": "Finish the math homework",
                "deadline": "2026-07-04",
                "constraints": [
                    "Only use knowledge from Chapter 10"
                ],
                "tools_needed": [
                    "N/A"
                ]
            },
            "missing_info": [],
            "questions": []
        }),
        #openAI call 3: the model return sub tasks after decomposition layer
        ai_fake_message({
            "status": "success",
            "sub_tasks":[
                {
                    "title": "review chapter 10",
                    "deadline": "2026-07-03",
                    "estimated_duration_minutes": 120,
                    "reason": "to better understand the content",
                    "depends_on": []
                },
                {
                    "title": "do chapter 10 Homework",
                    "deadline": "2026-07-04",
                    "estimated_duration_minutes": 60,
                    "reason": "this is the requirement",
                    "depends_on": []
                },
                {
                    "title": "review and double check",
                    "deadline": "2026-07-04",
                    "estimated_duration_minutes": 30,
                    "reason": "Make the homework correction better",
                    "depends_on": []
                }
            ]
        }),
        #openAI call4 : return sub tasks after structuring layer
        ai_fake_message({
            "status": "success",
            "sub_tasks": [
                {
                    "title": "Review Chapter 10",
                    "deadline": "2026-07-03",
                    "estimated_duration_minutes": 120,
                    "reason": "Review Chapter 10 to understand the concepts needed for the homework.",
                    "depends_on": []
                },
                {
                    "title": "Complete Chapter 10 Homework",
                    "deadline": "2026-07-04",
                    "estimated_duration_minutes": 60,
                    "reason": "Complete the assigned homework problems after reviewing the chapter.",
                    "depends_on": [
                        "Review Chapter 10"
                    ]
                },
                {
                    "title": "Review and Double-Check Answers",
                    "deadline": "2026-07-04",
                    "estimated_duration_minutes": 30,
                    "reason": "Check the homework for mistakes before submission.",
                    "depends_on": [
                        "Complete Chapter 10 Homework"
                    ]
                }
            ]
        }),
        #openAI call 5: the model return finalized sub-tasks after call feedback layer
        ai_fake_message({
            "status": "waiting_feedback",
            "sub_tasks":[
                {
                    "title": "review chapter 10",
                    "deadline": "2026-07-03",
                    "estimated_duration_minutes": 120,
                    "reason": "to better understand the content",
                    "depends_on": []
                },
                {
                    "title": "do chapter 10 Homework",
                    "deadline": "2026-07-03",
                    "estimated_duration_minutes": 80,
                    "reason": "this is the requirement",
                    "depends_on": []
                },
                {
                    "title": "review and double check",
                    "deadline": "2026-07-03",
                    "estimated_duration_minutes": 30,
                    "reason": "Make the homework correction better",
                    "depends_on": []
                }
            ]
        })
    ]
    #Stage 1: user sends a vague task description
    first_messages = [
        ChatMessage(
            id=1,
            role="user",
            content="Help me finish my math homework."
        )
    ]
    first_result = ai_assistance_control_center(first_messages)
    assert first_result["status"] == "needs_clarification"
    assert first_result["missing_info"] == ["deadline"]
    assert first_result["questions"] == ["when does the homework due?"]
    #Stage 2: user clarified the task and receive structued sub_tasks
    second_messages = [
        ChatMessage(
            id=1,
            role="user",
            content="Help me finish my math homework."
        ),
        ChatMessage(
            id=2,
            role="assistant",
            content="What is the final deadline?"
        ),
        ChatMessage(
            id=3,
            role="user",
            content="The deadline is July 4, 2026."
        ),
    ]
    second_result = ai_assistance_control_center(second_messages)
    assert second_result["status"] == "success"
    assert second_result["sub_tasks"][0]["title"] == "Review Chapter 10"
    
    #Stage 3, user send feedback
    messages = second_messages
    feedback = [
        ChatMessage(
            id = 4,
            role = "user",
            content = "I think I should finish all subtask in oneday"
        )
    ]
    tasks_after_feedback = {
        "sub_tasks":[
            {
                "title": "review chapter 10",
                "deadline": "2026-07-03",
                "estimated_duration_minutes": 120,
                "reason": "to better understand the content",
                "depends_on": []
            },
            {
                "title": "do chapter 10 Homework",
                "deadline": "2026-07-04",
                "estimated_duration_minutes": 60,
                "reason": "this is the requirement",
                "depends_on": []
            },
            {
                "title": "review and double check",
                "deadline": "2026-07-04",
                "estimated_duration_minutes": 30,
                "reason": "Make the homework correction better",
                "depends_on": []
            }
        ]
    }

    third_response = handle_feedback_improvement(messages, tasks_after_feedback, feedback)
    assert third_response["sub_tasks"][1]["estimated_duration_minutes"] == 80
    assert third_response["sub_tasks"][1]["deadline"] == "2026-07-03"
    