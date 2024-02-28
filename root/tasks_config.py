from celery import Celery
from kombu import Queue

celery = Celery("tasks", broker="amqp://localhost:5672/", backend="rpc://localhost:5672/")

celery.conf.task_queues = (
    Queue(name='default', routing_key='default'),
    Queue(name='receive_msgs', routing_key='receive_msgs'),
    Queue(name='send_msgs', routing_key='send_msgs'),
    Queue(name='failed_tasks', routing_key='failed_tasks')
)

celery.conf.task_routes = {
    'root.tasks.compo_api': {'queue': 'receive_msgs'},
    'root.tasks.all_api': {'queue': 'receive_msgs'},
    'root.tasks.get_user': {'queue': 'receive_msgs'},

    'root.tasks.use_data': {'queue': 'send_msgs'},
    'root.tasks.create_post': {'queue': 'send_msgs'},
    'root.tasks.get_created_post': {'queue': 'send_msgs'},

    'root.tasks.failed_tasks': {'queue': 'failed_tasks'}
}