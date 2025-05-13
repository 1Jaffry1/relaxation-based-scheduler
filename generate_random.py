import random

class Task:
    def __init__(self, id, arrival_time, burst_time, deadline, priority):
        self.id = id
        self.arrival_time = arrival_time
        self.burst_time = burst_time
        self.deadline = deadline
        self.priority = priority
        self.remaining_time = burst_time
        self.completion_time = None
        self.laxity = deadline - burst_time

def generate_random_taskset(
    num_tasks=10,
    arrival_time_range=(0, 20),
    burst_time_range=(1, 30),
    deadline_slack_range=(2, 10),
    priority_range=(1, 3)
):
    all_tasksets = []
    for ts_id in range(30):  # generate 10 tasksets
        taskset = []
        setsize = random.randint(3, num_tasks+1)
        for task_id in range(1, setsize):
            arrival_time = random.randint(*arrival_time_range)
            burst_time = random.randint(*burst_time_range)
            slack = random.randint(*deadline_slack_range)
            deadline = arrival_time + burst_time + slack
            priority = random.randint(*priority_range)
            task = (task_id, arrival_time, burst_time, deadline, priority)
            taskset.append(task)
        all_tasksets.append(taskset)
    return all_tasksets

# Generate random tasksets
random_tasksets = generate_random_taskset()

# Save to a Python file
with open('random_taskset.py', 'w') as f:
    f.write("from taskset import Task\ntasks = [\n")
    for taskset in random_tasksets:
        f.write("    [\n")
        for task in taskset:
            f.write(f"        Task{task},\n")
        f.write("    ],\n")
    f.write("]\n\n")
    f.write("SIMULATION_TIME = 100\n")

print("✅ Saved random tasksets to random_taskset.py!")
