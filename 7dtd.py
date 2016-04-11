import boto.ec2
import logging
import requests
import click
import yaml
import time

logging.basicConfig(level=logging.INFO)

class Server(object):
  def __init__(self):
    stream = file('config.yaml', 'r')
    self.cfg = yaml.load(stream)

    name_tag = '7dtd'
    filters = {"tag:Name": name_tag}

    if not self.cfg['aws']:
      logging.error("No AWS config found in config.yaml")
      raise SystemExit
    aws_config_options = {}
    aws_config_options.update(**self.cfg['aws'])
    try:
      self.conn = boto.ec2.connect_to_region(
        "us-west-2",
        **aws_config_options
      )
    except boto.provider.ProfileNotFoundError:
      logging.error("AWS profile not found")
      self.help()
      raise SystemExit


    try:
      reservations = self.conn.get_all_reservations(filters=filters)
      self.instance_id = reservations[0].instances[0].id
    except boto.exception.EC2ResponseError as e:
      raise SystemExit
    except Exception:
      logging.fatal(
          "no instance found in AWS EC2 with a name tag: {0}".format(name_tag))
      raise SystemExit

  def start(self):
    try:
      self.conn.start_instances(instance_ids=[self.instance_id])
    except boto.exception.EC2ResponseError as e:
      logging.warn("Server is not ready to be started. waiting 10 seconds and trying again.")
      time.sleep(10)
      self.start()
    logging.info("Starting server")

  def stop(self):
    stop_uri = 'http://{0}:5000/stop'.format(self.cfg['game_server']['host'])

    username = self.cfg['game_server']['stop_username']
    password = self.cfg['game_server']['stop_password']
    if self.is_game_running():
      try:
        r = requests.get(stop_uri, auth=(username, password))
      except requests.ConnectionError as e:
        if 'Connection refused' in  e.message[1]:
          logging.error('The rest service is not running on {0}'.format(
            self.cfg['game_server']['host']))
          raise SystemExit

    self.conn.stop_instances(instance_ids=[self.instance_id])
    logging.info("Stopping server")

  def help(self):
    pass

  def is_game_running(self):
    ''' An unfortunate way to check if the game is online
        Surely there is a better way to do this
    '''
    try:
      r = requests.get('http://{0}:26900'.format(self.cfg['game_server']['host']))
    except requests.ConnectionError as e:
      if 'Connection refused' in  e.message[1]:
        return False

    return True

  def status(self):
    statuses = self.conn.get_all_instance_status(instance_ids=self.instance_id)
    if len(statuses) == 1:
      status = statuses[0]
      state = status.state_name
    elif len(statuses) == 0:
      logging.info("Server is offline")
      raise SystemExit
    else:
      logging.warn("More than 1 instances found, something is wrong")
      raise SystemExit

    if state == 'running':
      if not self.is_game_running():
        logging.info("Server is running but game service is offline")
      else:
        logging.info(
            "EVERYTHING IS OKAY. Server is running and game service is online")

@click.command()
@click.argument('operation', nargs=1, type=click.Choice(
  ['start', 'stop', 'status']
  ))
def main(operation):
  ''' Start/Stop 7 Days to Die game server
  '''
  server = Server()
  op = getattr(server, operation)
  op()

if __name__ == '__main__':
      main()
