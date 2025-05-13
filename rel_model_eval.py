import heapq
import joblib
import csv
from ML.taskset import tasks  # <- Import your random generated tasksets
from ML.taskset import SIMULATION_TIME  # <- Import SIMULATION_TIME
import warnings

warnings.filterwarnings("ignore")
# Load trained Random Forest model
model = joblib.load('relaxation_rf_model.pkl')

NUM_CORES = 2
CONTEXT_SWITCH_TIME = 3

correct_predictions = 0
total_predictions = 0
grand_total_deadline_misses = 0
grand_total_preemptions = 0
grand_total_utilization = 0

summary_log = []

taskset_id = -1

for taskset_ in tasks:
    taskset_id += 1
    unarrived_tasks = taskset_
    current_time = 0
    deadline_misses = 0
    preemptions = 0
    busy_time = 0
    completed_tasks = []
    missed_priorities = []
    deadline_miss_times = []   # <-- MTBF: Track when deadline misses occur

    active_tasks = []
    cores = [None] * NUM_CORES

    print(f"\nEvaluating Taskset #{taskset_id}\n t  1  |  2\n------|---")

    for current_time in range(SIMULATION_TIME):
        for task in unarrived_tasks:
            if task.arrival_time == current_time:
                heapq.heappush(active_tasks, task)

        unarrived_tasks = [task for task in unarrived_tasks if task.arrival_time > current_time]

        for core in range(NUM_CORES):
            if cores[core] is None and active_tasks:
                task = active_tasks[0]

                features = [[
                    taskset_id,
                    current_time,
                    task.remaining_time,
                    task.deadline,
                    getattr(task, 'priority', 0),
                    task.laxity
                ]]

                predicted_core = model.predict(features)[0]

                if cores[predicted_core] is None:
                    assigned_core = predicted_core
                else:
                    if cores[predicted_core].remaining_time > task.remaining_time:
                        preempted_task = cores[predicted_core]
                        heapq.heappush(active_tasks, preempted_task)
                        cores[predicted_core] = None
                        preemptions += 1
                    assigned_core = predicted_core if cores[predicted_core] is None else core

                ideal_core = core
                if assigned_core == ideal_core:
                    correct_predictions += 1
                total_predictions += 1

                task = heapq.heappop(active_tasks)
                cores[assigned_core] = task

        for core in range(NUM_CORES):
            if cores[core]:
                cores[core].remaining_time -= 1
                busy_time += 1

                if cores[core].remaining_time <= 0:
                    cores[core].completion_time = current_time
                    completed_tasks.append(cores[core])

                    if cores[core].completion_time > cores[core].deadline:
                        deadline_misses += 1
                        missed_priorities.append(getattr(cores[core], 'priority', -1))
                        deadline_miss_times.append(current_time)   # <-- MTBF

                    cores[core] = None

        core_status = [str(cores[i].id) if cores[i] else "-" for i in range(NUM_CORES)]
        print(f"{current_time}  {core_status[0]}  |  {core_status[1]}")

    for task in active_tasks:
        if task.remaining_time > 0:
            deadline_misses += 1
            missed_priorities.append(getattr(task, 'priority', -1))
            deadline_miss_times.append(current_time)   # <-- MTBF
            print(f"⚠️ Task {task.id} did not complete and missed its deadline.")

    # --- MTBF Calculation ---
    if deadline_misses > 1:
        intervals = [deadline_miss_times[i+1] - deadline_miss_times[i] for i in range(len(deadline_miss_times)-1)]
        mtbf = sum(intervals) / len(intervals)
    elif deadline_misses == 1:
        mtbf = SIMULATION_TIME
    else:
        mtbf = float('1000')

    taskset_utilization = (busy_time / (SIMULATION_TIME * NUM_CORES)) * 100

    summary_log.append([
        taskset_id,
        preemptions,
        deadline_misses,
        len(completed_tasks),
        f"{taskset_utilization:.2f}",
        f"{mtbf:.2f}",
        ','.join(str(p) for p in missed_priorities)
    ])

    grand_total_deadline_misses += deadline_misses
    grand_total_preemptions += preemptions
    grand_total_utilization += busy_time

# Final Evaluation
print("\nFinal Evaluation Results")
print(f"Total Predictions: {total_predictions}")
print(f"Correct Predictions: {correct_predictions}")
accuracy = (correct_predictions / total_predictions) * 100 if total_predictions > 0 else 0
print(f"Core Assignment Accuracy: {accuracy:.2f}%")

print("\nFinal Grand Totals:")
print(f"Grand Total Deadline Misses: {grand_total_deadline_misses}")
print(f"Grand Total Preemptions: {grand_total_preemptions}")
grand_total_utilization = (grand_total_utilization / (SIMULATION_TIME * NUM_CORES * len(tasks))) * 100
print(f"Grand Total CPU Utilization: {grand_total_utilization:.2f}%")

# Save to CSV
with open('../RF_taskset_summary.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([
        'Taskset_ID', 'Preemptions', 'Deadline_Misses', 'Completed_Tasks',
        'CPU_Utilization(%)', 'MTBF_Cycles', 'Missed_Task_Priorities'
    ])
    writer.writerows(summary_log)

print("\n✅ Saved RF taskset summaries to 'RF_taskset_summary.csv'")
