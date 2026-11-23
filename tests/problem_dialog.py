"""AppTest helpers for driving the shared "Edit problems" dialog."""


def open_problems(app, key):
    app.button(key=f"edit_problems_{key}").click().run()
    return app


def fill_new_problem(app, key, content, *, topic="Logic", reference="Solution", points=None):
    selector = app.selectbox(key=f"selected_problem_{key}")
    if selector.value != "new":
        selector.set_value("new").run()
    app.text_area(key=f"new_content_{key}").set_value(content)
    app.text_input(key=f"new_problem_{key}_topic").set_value(topic)
    app.text_area(key=f"new_problem_{key}_reference_answer").set_value(reference)
    if points is not None:
        app.number_input(key=f"new_problem_{key}_points").set_value(points)
    return app


def add_problem(app, key, content, **fields):
    fill_new_problem(app, key, content, **fields)
    next(button for button in app.button if button.label == "Add problem").click().run()
    return app


def close_problems(app, key):
    app.button(key=f"problem_manager_done_{key}").click().run()
    return app
