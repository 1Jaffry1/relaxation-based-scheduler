import matplotlib.pyplot as plt

def parse_history(history_text):
    lines = history_text.strip().split('\n')
    data = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('t') or '-'*3 in line:
            continue  # Skip header and separators
        if '|' in line:
            time_part, right_part = line.split('|', 1)
            left = time_part.strip().split()
            right = right_part.strip().split()

            if len(left) >= 2:
                time = int(left[0])
                core0 = left[1] if left[1] != '-' else None
                core1 = right[0] if right and right[0] != '-' else None
                data.append((time, core0, core1))
    return data

def plot_schedule_with_labels(data, title="Task Scheduling History"):
    fig, ax = plt.subplots(figsize=(14, 2))  # Smaller height (2 instead of 5)

    color_palette = plt.cm.get_cmap('tab20')  # 20 colors
    colors = {}

    bar_height = 0.8  # Make bars thinner

    core_positions = {0: 0.5, 1: -0.5}  # Core 0 above, Core 1 below (closer together)

    for core_idx in [0, 1]:
        current_task = None
        start_time = None

        for i, (time, core0, core1) in enumerate(data):
            task_id = core0 if core_idx == 0 else core1

            if task_id != current_task:
                if current_task is not None:
                    end_time = time
                    if current_task not in colors:
                        colors[current_task] = color_palette(len(colors) % 20)
                    width = end_time - start_time
                    ax.barh(
                        y=core_positions[core_idx],
                        width=width,
                        left=start_time,
                        height=bar_height,
                        color=colors[current_task],
                        edgecolor='black'
                    )
                    if current_task is not None:
                        ax.text(
                            x=start_time + width/2,
                            y=core_positions[core_idx],
                            s=str(current_task),
                            va='center',
                            ha='center',
                            fontsize=8,
                            color='black',
                            fontweight='bold'
                        )
                current_task = task_id
                start_time = time

        if current_task is not None and start_time is not None:
            end_time = data[-1][0] + 1
            if current_task not in colors:
                colors[current_task] = color_palette(len(colors) % 20)
            width = end_time - start_time
            ax.barh(
                y=core_positions[core_idx],
                width=width,
                left=start_time,
                height=bar_height,
                color=colors[current_task],
                edgecolor='black'
            )
            ax.text(
                x=start_time + width/2,
                y=core_positions[core_idx],
                s=str(current_task),
                va='center',
                ha='center',
                fontsize=8,
                color='black',
                fontweight='bold'
            )

    ax.set_yticks([core_positions[0], core_positions[1]])
    ax.set_yticklabels(['Core 0', 'Core 1'])
    ax.set_xlabel('Time')
    ax.set_title(title, pad=20)
    ax.grid(True, axis='x', linestyle='--', alpha=0.7)

    ax.set_ylim(-1, 1)  # Tight vertical limit
    plt.tight_layout()
    import matplotlib.ticker as ticker

    ax.xaxis.set_major_locator(ticker.MultipleLocator(1))  # Show every 1 unit
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())  # Optional: minor ticks
    plt.show()

# === Example Usage ===

history_text = """
t  1  |  2
------|---
0  1  |  -
1  1  |  2
2  1  |  2
3  1  |  2
4  4  |  5
5  4  |  5
6  6  |  5
7  6  |  7
10  3  |  -
"""

parsed_data = parse_history(history_text)
plot_schedule_with_labels(parsed_data, title="ENF-S Scheduler ")
