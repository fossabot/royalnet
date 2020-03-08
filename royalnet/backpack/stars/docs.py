import json
from typing import *
from royalnet.constellation import PageStar
from royalnet.constellation.api import ApiStar
from starlette.requests import Request
from starlette.responses import Response, HTMLResponse
from royalnet.version import semantic


class DocsStar(PageStar):
    path = "/docs"

    async def page(self, request: Request) -> Response:
        spec = json.dumps({
            "swagger": "2.0",
            "info": {
                "description": "Autogenerated Royalnet API documentation",
                "title": "Royalnet",
                "version": f"{semantic}",
                "paths": [star.swagger() for star in self.constellation.stars if isinstance(star, ApiStar)]
            }
        })

        return HTMLResponse(
            f"""
            <html lang="en">
                <head>
                    <title>Royalnet Docs</title>
                    <script src="https://unpkg.com/swagger-ui-dist@3/swagger-ui-bundle.js"></script>
                </head>
                <body>
                    <div id="docs"/>
                    <script>
                        const ui = SwaggerUIBundle({{
                            spec: {spec}
                            dom_id: '#docs',
                            presets: [
                                SwaggerUIBundle.presets.apis,
                            ],
                        }})
                    </script>
                </body>
            </html>
            """
        )
