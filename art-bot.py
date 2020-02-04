#!/usr/bin/python3

from collections import namedtuple
import os
import slack
import pprint
import re
import koji

BOT_ID = 'UD5JGDRC5'
AT_BOT_ID = f'<@>{BOT_ID}'


SlackOutput = namedtuple('SlackOutput', 'say snippet')


def get_help(so):
    so.say("""Here are questions I can answer...
- What rpms are used in {image-nvr}?
""")


def brew_list_components(koji_api, nvr):
    build = koji_api.getBuild(nvr, strict=True)
    components = set()
    for archive in koji_api.listArchives(build['id']):
        for rpm in koji_api.listRPMs(imageID=archive['id']):
            components.add('{nvr}.{arch}'.format(**rpm))
    return components


def list_components(so, nvr):
    so.say('Sure.. let me check on {}'.format(nvr))
    so.snippet(payload='\n'.join(brew_list_components(koji_api, nvr)),
               intro='The following rpms are used',
               filename='{}-rpms.txt'.format(nvr))


@slack.RTMClient.run_on(event='message')
def respond(**payload):
    data = payload['data']
    web_client = payload['web_client']

    print('DATA')
    pprint.pprint(data)

    if 'user' not in data:
        # This message was not from a user; probably the bot hearing itself
        return

    from_channel = data['channel']

    # Get the id of the Slack user associated with the incoming event
    user_id = data['user']
    text = data['text']

    if user_id == BOT_ID:
        # things like snippets may look like they are from normal users; if it is from us, ignore it.
        return

    am_i_mentioned = AT_BOT_ID in text

    if am_i_mentioned:
        text = text.replace(AT_BOT_ID, '').strip()

    text = ' '.join(text.split())  # Replace different whitespace with single space
    text = text.rstrip('?')  # remove any question marks from the end

    response = web_client.im_open(user=user_id)
    direct_message_channel_id = response["channel"]["id"]

    said_something = False

    def say(thing):
        nonlocal said_something
        said_something = True
        web_client.chat_postMessage(
            channel=direct_message_channel_id,
            text=thing,
        )

    def snippet(payload, intro=None, filename=None, filetype=None):
        nonlocal said_something
        said_something = True
        print('Called with payload: {}'.format(payload))
        r = web_client.files_upload(
            initial_comment=intro,
            channels=direct_message_channel_id,
            content=payload,
            filename=filename,
            filetype=filetype,
        )
        print('Response: ')
        pprint.pprint(r)

    so = SlackOutput(say=say, snippet=snippet)

    # We only want to respond if in a DM channel or we are mentioned specifically in another channel
    if from_channel == direct_message_channel_id or am_i_mentioned:

        if re.match(r'^help$', text, re.I):
            get_help(so)

        m = re.match(r'^what rpms are used in (?P<nvr>[\w.-]+)$', text, re.I)
        if m:
            list_components(so, **m.groupdict())

        if not said_something:
            say("Sorry, I don't know how to help with that.")


koji_api = koji.ClientSession('https://brewhub.engineering.redhat.com/brewhub', opts={'serverca': '/etc/pki/brew/legacy.crt'})

slack_token = os.environ["SLACK_API_TOKEN"]
rtm_client = slack.RTMClient(token=slack_token)
rtm_client.start()