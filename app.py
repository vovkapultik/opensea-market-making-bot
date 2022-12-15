from helpers import managers

# floor - starting floor price
# step in percents, 1.05 == 5%
# orders - concurrent orders number
# schema - order distribution schema
# period - how long bot will sleep between iterations
# TODO: just start it, logs will cover everything

# TODO: take a look on helpers/managers.py line 99.
#  No .env so re-hardcode another value.

orchestrator = managers.Orchestrator(
    floor=0.30,
    step=1.05,
    orders=8,
    schema=[100, 200, 250, 100, 90, 120, 100, 70, 0, 0, 0, 0, 0, 0, 0, 0],
    period=2
)

orchestrator.start()