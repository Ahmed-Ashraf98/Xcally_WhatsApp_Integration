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

    'root.services.whatsapp_services.wa_get_media_details': {'queue': 'receive_msgs'},
    'root.services.whatsapp_services.wa_download_media': {'queue': 'receive_msgs'},
    'root.services.whatsapp_services.wa_write_read_file_data': {'queue': 'receive_msgs'},

    'root.services.xcally_services.xc_get_attachment_details': {'queue': 'receive_msgs'},
    'root.services.xcally_services.xc_download_attachment': {'queue': 'receive_msgs'},
    'root.services.xcally_services.xc_write_read_file_data': {'queue': 'receive_msgs'},


    'root.services.whatsapp_services.wa_upload_media_handler': {'queue': 'send_msgs'},
    'root.services.whatsapp_services.wa_send_message_to_whatsapp_user': {'queue': 'send_msgs'},

    'root.services.xcally_services.xc_upload_attachment': {'queue': 'send_msgs'},
    'root.services.xcally_services.send_message_to_xcally_channel': {'queue': 'send_msgs'},

    'root.tasks.failed_tasks': {'queue': 'failed_tasks'}
}