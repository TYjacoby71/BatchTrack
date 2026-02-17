from flask import Blueprint

batches_bp = Blueprint("batches", __name__, template_folder="templates")

# Import routes to register them
from . import add_extra, cancel_batch, finish_batch, routes, start_batch
