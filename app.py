import asyncio
import json
import os

import boto3
import strawberry
from mangum import Mangum
from strawberry.asgi import GraphQL
from asgi_cors import asgi_cors


GQL_CONNECTION_ACK = "connection_ack"
GQL_DATA = "data"


@strawberry.type
class Query:
    @strawberry.field
    def hello() -> str:
        return "world"


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def count(self, target: int = 100) -> int:
        for i in range(target):
            yield i
            await asyncio.sleep(0.5)


schema = strawberry.Schema(Query, subscription=Subscription)

app = GraphQL(schema)
app = asgi_cors(app, allow_all=True)

handler = Mangum(app)

HTML = """
<!DOCTYPE html>
<html>
  <head>
    <title>Strawberry GraphiQL</title>
    <style>
      html,
      body {
        height: 100%;
        margin: 0;
        overflow: hidden;
        width: 100%;
      }

      #graphiql {
        height: 100vh;
      }
    </style>

    <link
      rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/graphiql-with-extensions@0.14.3/graphiqlWithExtensions.css"
      integrity="sha384-GBqwox+q8UtVEyBLBKloN5QDlBDsQnuoSUfMeJH1ZtDiCrrk103D7Bg/WjIvl4ya"
      crossorigin="anonymous"
    />
    <script
      src="https://cdn.jsdelivr.net/npm/whatwg-fetch@2.0.3/fetch.min.js"
      integrity="sha384-dcF7KoWRaRpjcNbVPUFgatYgAijf8DqW6NWuqLdfB5Sb4Cdbb8iHX7bHsl9YhpKa"
      crossorigin="anonymous"
    ></script>
    <script
      src="https://cdn.jsdelivr.net/npm/react@16.8.6/umd/react.production.min.js"
      integrity="sha384-qn+ML/QkkJxqn4LLs1zjaKxlTg2Bl/6yU/xBTJAgxkmNGc6kMZyeskAG0a7eJBR1"
      crossorigin="anonymous"
    ></script>
    <script
      src="https://cdn.jsdelivr.net/npm/react-dom@16.8.6/umd/react-dom.production.min.js"
      integrity="sha384-85IMG5rvmoDsmMeWK/qUU4kwnYXVpC+o9hoHMLi4bpNR+gMEiPLrvkZCgsr7WWgV"
      crossorigin="anonymous"
    ></script>
    <script
      src="https://cdn.jsdelivr.net/npm/graphiql-with-extensions@0.14.3/graphiqlWithExtensions.min.js"
      integrity="sha384-TqI6gT2PjmSrnEOTvGHLad1U4Vm5VoyzMmcKK0C/PLCWTnwPyXhCJY6NYhC/tp19"
      crossorigin="anonymous"
    ></script>

    <!-- breaking changes in subscriptions-transport-ws since 0.9.0 -->
    <script src="https://cdn.jsdelivr.net/npm/subscriptions-transport-ws@0.8.3/browser/client.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/graphiql-subscriptions-fetcher@0.0.2/browser/client.js"></script>
  </head>

  <body>
    <div id="graphiql"></div>
    <script>
      var fetchURL = "https://s44ga0xlmh.execute-api.us-east-1.amazonaws.com";

      function httpUrlToWebSockeUrl(url) {
        return url.replace(/(http)(s)?\:\/\//, "ws$2://");
      }

      function graphQLFetcher(graphQLParams) {
        var headers = {
          Accept: "application/json",
          "Content-Type": "application/json"
        };

        return fetch(fetchURL, {
          method: "post",
          headers: headers,
          body: JSON.stringify(graphQLParams)
        })
          .then(function (response) {
            return response.text();
          })
          .then(function (responseBody) {
            try {
              return JSON.parse(responseBody);
            } catch (error) {
              return responseBody;
            }
          });
      }

      var subscriptionsEndpoint = httpUrlToWebSockeUrl(
        "wss://16huvhioc7.execute-api.us-east-1.amazonaws.com/dev"
      );
      var subscriptionsEnabled = true;

      const subscriptionsClient = subscriptionsEnabled
        ? new window.SubscriptionsTransportWs.SubscriptionClient(
            subscriptionsEndpoint,
            {
              reconnect: true
            }
          )
        : null;

      const graphQLFetcherWithSubscriptions = window.GraphiQLSubscriptionsFetcher.graphQLFetcher(
        subscriptionsClient,
        graphQLFetcher
      );

      ReactDOM.render(
        React.createElement(GraphiQLWithExtensions.GraphiQLWithExtensions, {
          fetcher: graphQLFetcherWithSubscriptions
        }),
        document.getElementById("graphiql")
      );
    </script>
  </body>
</html>
"""


async def graphiql_app(scope, receive, send):
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"text/html; charset=utf-8"]],
        }
    )
    await send({"type": "http.response.body", "body": HTML.encode("utf-8")})


graphiql_app = asgi_cors(graphiql_app, allow_all=True)
graphiql_app_handler = Mangum(graphiql_app)


def send_message(event, data):
    data = json.dumps(data)

    endpoint = os.environ["WEBSOCKET_API_ENDPOINT"]

    connection_id = event["requestContext"].get("connectionId")

    gateway_api = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint)
    gateway_api.post_to_connection(
        ConnectionId=connection_id, Data=data.encode("utf-8")
    )


def ws_connection(event, context):
    return {"statusCode": 200, "headers": {"Sec-WebSocket-Protocol": "graphql-ws"}}


def ws_message(event, context):
    send_message(event, {"type": GQL_CONNECTION_ACK})
    send_message(event, {"type": GQL_DATA, "payload": {"data": "example"}, "id": "1"})

    return {"statusCode": 200}
