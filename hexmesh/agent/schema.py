#        _.-------._
#    .-''     |     ''-.
#  .'  \      |      /  '.     _                                         _
# /     +-----+-----+     \   | |__   ___  __  __  _ __ ___   ___  ___  | |__
# |     |     |     |     |   | '_ \ / _ \ \ \/ / | '_ ` _ \ / _ \/ __| | '_ \
# |-----+-----+-----+-----|   | | | |  __/  >  <  | | | | | |  __/\__ \ | | | |
# |     |     |     |     |   |_| |_|\___| /_/\_\ |_| |_| |_|\___||___/ |_| |_|
# \     +-----+-----+     /
#  '.  /      |      \  .'    structured all-hex meshes for pipe networks
#    '-..     |     ..-'
#        '---------'
#
"""``python3 -m hexmesh.agent.schema``: print the JSON Schema of the saved
``hexmesh.assembly`` description (task 0095).  The generator is
``hexmesh.agent._schema``; ``hexmesh.agent.schema()`` returns it as a dict.
"""

from ._schema import dumps, schema

__all__ = ["dumps", "schema"]

if __name__ == "__main__":
    print(dumps(), end="")
