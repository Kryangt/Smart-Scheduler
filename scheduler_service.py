from google_tasks_service import create_task, get_tasks_list
from google_events_service import get_events, create_event

def schedule(tasks):
    #use dynamic programing to find the the best arrangement of tasks

    #1. Preprocess tasks. If the lasting time of tasks exceed 1 hour. For example 1.5 hour, split into two tasks, each has 1 hour， get n num of tasks
    #2. Take 1 hour as a unit, and searching for n free slots
    #3. Let's take first task out, so i = 0, j = 0, now we have to decide should arrange it
    #4. Calculate the lateness of this task. L_i = D_i < F_j? F_j - D_i : 0    where F_j represents the end time of F_j
    #5. then at i and j, we have dp[i][j] = min(dp[i-1][j-1] + L_i, dp[i-1][j])