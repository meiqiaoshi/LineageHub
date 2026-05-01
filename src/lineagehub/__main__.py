"""Allow ``python -m lineagehub`` (same entry points as the ``lineagehub`` console script)."""

from lineagehub.cli import main

raise SystemExit(main())
