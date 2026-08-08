# Bike Maintenance Tracker

Besides tracking your activities, you can also track routine maintenance, upgrades, and repairs for your bikes and other equipment.

## Data model

There are maintenance trackers tailored for professional athletes, like [ProBikeGarage](https://www.probikegarage.com/). The intention here is to have something for people who take care of their bikes themselves and think of it as a whole bike and not a set of components that get switched between bikes. If in the future there is demand for component tracking, we can of course think of adding it.

In the current state, we have these entities:

- **Equipment**: A bike, a pair of running shoes. Each *activity* can be associated with exactly one _equipment_. The equipment's usage (mileage) is computed as the sum of all activities associated with the _equipment_, plus a manual offset from non-tracked activities.
- **Maintenance Action**: A deliberately broad action that was done on the _equipment_. It has a title, description (Markdown) and is associated with a date, a usage, a cost and optionally photos.
- **Recurring Task**: A task is something that needs to be checked or done on a specific _equipment_, but isn't a _maintenance action_ in itself. These are things like “apply chain lube”, “check tire pressure”. Each _task_ has a title, an interval in days and/or an interval in kilometers.
- **Task Execution**: When a _task_ is executed, it is logged with the date and the mileage of the _equipment_ when it was executed.

### Recurring tasks versus maintenance actions

The fundamental distinction is between *tasks* and *maintenance actions*.

A **task** is a recurring activity. It can be triggered by time or by distance (kilometers ridden) and does not incur costs. A prime example is checking for chain wear every 500 km.

A **maintenance action** is a one-off activity that typically incurs costs. Think of a spare part that you buy and install on your bike.

Some examples:

| Situation | Entity |
| --- | --- |
| Checking chain wear every 500 km | Task |
| Replacing a worn-out chain | Maintenance action |
| Checking tire wear every 1000 km | Task |
| Replacing a worn-out tire | Maintenance action |
| Buying a new saddle | Maintenance action |
| Taking the bike to a repair shop | Maintenance action |

### Limitations

Geo Activity Playground only tracks the usage of entire bicycles, not of individual components. If you frequently swap parts (like cassettes) between bikes and want to monitor their specific mileage, have a look at other tools like [ProBikeGarage](https://www.probikegarage.com/).

It is also less suitable for managing a family fleet, because for it to work properly the bikes' mileage would need to be logged in Geo Activity Playground, which goes against its core logic.

## Usage

### Recurring tasks

1. Go to *Statistics → Equipment*.
2. Go into one of your equipments.
3. Select *Add task*.
4. Assign a name and specify whether the task should recur every *x* kilometers and/or every *y* days.

In the equipment section you can then see which tasks have been performed and which are overdue. Overdue tasks are highlighted in red and displayed on the dashboard. Once a task is completed, you can mark it as done with a single click; the time or mileage interval then resets. You can also add a text note here.

### Maintenance actions

1. Go to *Statistics → Equipment*.
2. Go into one of your equipments.
3. Select *Add action*.
4. Enter all relevant details and attach a photo.

## Statistics

Under *Statistics → Maintenance* you find your maintenance statistics. These display metrics such as annual costs or costs per bike.

## Notes

- The “cost vs. usage” statistic is most meaningful if you also include the purchase price of your bike as a maintenance action. This allows the system to calculate based on total costs rather than just repair expenses.
- If you do not perform your own bike maintenance but instead take your bike to a shop for everything, including inspections, simply log a maintenance action with the inspection costs.
- It may sound a bit unusual at first, but you can track breakdowns as maintenance actions, not just upgrades or repairs. For instance, a flat tire that you patched yourself at no cost can be logged as a maintenance action with the note “flat tire”.
- You can of course log tasks earlier or later than scheduled. If you want to check your bike before a vacation, you can do so even if the “required” mileage hasn't been reached yet. Likewise, nothing forces you to check the chain exactly when a self-defined mileage limit is hit.
- Geo Activity Playground works with any activity that generates a GPS track. While the core logic is designed for bicycles, it should also be suitable for canoes, running shoes and—theoretically—even paragliders. You are the expert on your sport and your equipment.
