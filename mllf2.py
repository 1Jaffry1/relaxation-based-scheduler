import heapq
from copy import copy
import csv

epsilon = 1e-9
NUM_CORES = 2
CONTEXT_SWITCH_TIME = 3

import taskset
from taskset import SIMULATION_TIME

class Task:
    def __init__(self, id, arrival_time, burst_time, deadline, priority=0):
        self.id = id
        self.arrival_time = arrival_time
        self.burst_time = burst_time
        self.deadline = deadline
        self.priority = priority
        self.remaining_time = burst_time
        self.completion_time = None

    def __lt__(self, other):
        # Use current_time defined in global scope for laxity
        return (self.deadline - current_time - self.remaining_time) < (other.deadline - current_time - other.remaining_time)

    @property
    def laxity(self):
        # current_time must be defined in the global scope when this is called
        return self.deadline - current_time - self.remaining_time

    def __repr__(self):
        return f'Task: {self.id}, Laxity: {self.laxity}, remaining: {self.remaining_time}'

# --- Global Statistics ---
grand_total_deadline_misses = 0
grand_total_preemptions = 0
grand_total_data_transfers = 0

summary_log = []
missed_priorities_log = []

taskset_id = -1

for taskset_ in taskset.tasks:
    taskset_id += 1
    current_time = 0
    preemptions = 0
    deadline_misses = 0
    data_transfer_count = 0
    busy_time = 0
    history = []
    unarrived_tasks = taskset_
    taskset_size = len(unarrived_tasks)

    tasks = []
    completed_tasks = []
    missed_priorities = []
    deadline_miss_times = []  # Track when deadline misses occur

    cores = [None] * NUM_CORES

    print(f"\n🔵 MLLF: Taskset #{taskset_id}\nt  1  |  2\n------|---")

    for current_time in range(SIMULATION_TIME):
        # --- Task Arrival ---
        for task in unarrived_tasks:
            if task.arrival_time == current_time:
                heapq.heappush(tasks, copy(task))
                data_transfer_count += 1

        unarrived_tasks = [task for task in unarrived_tasks if task.arrival_time > current_time]

        # --- Assign to Cores ---
        for core in range(NUM_CORES):
            if cores[core] is None and tasks:
                cores[core] = heapq.heappop(tasks)
                data_transfer_count += 1

        # --- Preemption Logic ---
        if tasks:
            task = tasks[0]

            for core in range(NUM_CORES):
                if cores[core] is None:
                    cores[core] = heapq.heappop(tasks)
                    data_transfer_count += 1
                    break

            worst_core = None
            max_laxity = -1
            for core in range(NUM_CORES):
                if cores[core] is not None and cores[core].laxity > max_laxity:
                    max_laxity = cores[core].laxity
                    worst_core = core

            if worst_core is not None and task.laxity < cores[worst_core].laxity:
                task_out = cores[worst_core]
                task_in = heapq.heappop(tasks)
                cores[worst_core] = task_in
                heapq.heappush(tasks, task_out)
                preemptions += 1
                data_transfer_count += 2
                cores[worst_core].remaining_time += CONTEXT_SWITCH_TIME
                history.append(f"Time {current_time}: Preempted {task_out.id} with {task_in.id} on Core {worst_core}")

        # --- Task Execution ---
        for core in range(NUM_CORES):
            if cores[core] is not None:
                cores[core].remaining_time -= 1
                busy_time += 1

                if cores[core].remaining_time <= 0:
                    cores[core].completion_time = current_time
                    completed_tasks.append(cores[core])

                    if cores[core].completion_time > cores[core].deadline:
                        deadline_misses += 1
                        deadline_miss_times.append(current_time)
                        missed_priorities.append(getattr(cores[core], 'priority', 'N/A'))

                    cores[core] = None

        core_status = [str(cores[i].id) if cores[i] else "-" for i in range(NUM_CORES)]
        print(f"{current_time}  {core_status[0]}  |  {core_status[1]}")

    # --- Check Incomplete Tasks ---
    for task in tasks:
        if task.remaining_time > 0:
            deadline_misses += 1
            deadline_miss_times.append(current_time)
            missed_priorities.append(getattr(task, 'priority', 'N/A'))
            print(f"⚠️ Task {task.id} did not complete and missed deadline.")

    # --- MTBF Calculation ---
    if deadline_misses > 1:
        intervals = [deadline_miss_times[i+1] - deadline_miss_times[i] for i in range(len(deadline_miss_times)-1)]
        mtbf = sum(intervals) / len(intervals)
    elif deadline_misses == 1:
        mtbf = SIMULATION_TIME  # Only one failure, so MTBF is full simulation time
    else:
        mtbf = float('1000')

    print("\n📜 Preemption History:")
    for event in history:
        print(event)

    print("\n🎯 Completion Summary:")
    for task in completed_tasks:
        if task.completion_time > task.deadline:
            print(f"❌ MISS: Task {task.id} completed at {task.completion_time} after deadline {task.deadline}")
        else:
            print(f"✅ DONE: Task {task.id} completed at {task.completion_time} before deadline {task.deadline}")

    print(f"\n📈 Total Preemptions: {preemptions}")
    print(f"💥 Total Deadline Misses: {deadline_misses}")
    print(f"🔄 Total Data Transfers: {data_transfer_count}")
    print(f"⏱️ MTBF (Deadline Misses): {mtbf:.2f} cycles")

    grand_total_deadline_misses += deadline_misses
    grand_total_preemptions += preemptions
    grand_total_data_transfers += data_transfer_count

    taskset_utilization = (busy_time / (SIMULATION_TIME * NUM_CORES)) * 100

    summary_log.append([
        taskset_id,
        preemptions,
        deadline_misses,
        data_transfer_count,
        f"{taskset_utilization:.2f}",
        mtbf
    ])
    missed_priorities_log.append((taskset_id, missed_priorities))

# --- Final Statistics ---

print("\n🚀 Final Grand Totals for MLLF:")
print(f"💥 Grand Total Deadline Misses: {grand_total_deadline_misses}")
print(f"🔄 Grand Total Preemptions: {grand_total_preemptions}")
print(f"🔁 Grand Total Data Transfers: {grand_total_data_transfers}")
print(f"⚡ Overall CPU Utilization: {taskset_utilization:.2f}%")

print("\n🧾 Priorities of Missed Deadline Tasks (per Taskset):")
for tid, plist in missed_priorities_log:
    print(f"Taskset {tid}: Missed Priorities -> {plist}")

with open('../mllf_taskset_summary.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([
        'Taskset_ID',
        'Preemptions',
        'Deadline_Misses',
        'Data_Transfers',
        'CPU_Utilization(%)',
        'MTBF_Cycles',
        'Missed_Task_Priorities'
    ])
    for summary, (_, priorities) in zip(summary_log, missed_priorities_log):
        writer.writerow(summary + [','.join(str(p) for p in priorities)])

print("\n✅ Saved MLLF taskset summaries with missed priorities and MTBF to 'mllf_taskset_summary.csv'")
