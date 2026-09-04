"""The site's starting copy.

These are data modules, not management commands. They used to live in
`management/commands/`, where Django listed them as commands and running one
crashed, because a module in that package is expected to define a `Command`
class. `manage.py seed_content` imports them from here instead.
"""
