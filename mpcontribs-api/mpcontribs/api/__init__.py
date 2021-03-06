# -*- coding: utf-8 -*-
"""Flask App for MPContribs API"""
from gevent import monkey

monkey.patch_all()

import os
import logging
import boto3

from importlib import import_module
from flask import Flask, current_app
from flask_marshmallow import Marshmallow
from flask_mongoengine import MongoEngine
from flask_mongorest import register_class
from flask_log import Logging
from flask_sse import sse
from flask_compress import Compress
from flasgger.base import Swagger

from mongoengine import ValidationError
from mongoengine.base.datastructures import BaseDict
from itsdangerous import URLSafeTimedSerializer
from string import punctuation
from boltons.iterutils import remap, default_enter


delimiter, max_depth = ".", 4
invalidChars = set(punctuation.replace("*", ""))
invalidChars.add(" ")

for mod in [
    "matplotlib",
    "toronado.cssutils",
    "selenium.webdriver.remote.remote_connection",
    "botocore",
    "websockets.protocol",
    "asyncio",
]:
    log = logging.getLogger(mod)
    log.setLevel("INFO")

logger = logging.getLogger("app")
sns_client = boto3.client("sns")


def enter(path, key, value):
    if isinstance(value, BaseDict):
        return dict(), value.items()
    elif isinstance(value, list):
        dot_path = delimiter.join(list(path) + [key])
        raise ValidationError(f"lists not allowed ({dot_path})!")

    return default_enter(path, key, value)


def valid_key(key):
    for char in key:
        if char in invalidChars:
            raise ValidationError(f"invalid character {char} in {key}")


def visit(path, key, value):
    key = key.strip()

    if len(path) + 1 > max_depth:
        dot_path = delimiter.join(list(path) + [key])
        raise ValidationError(f"max nesting ({max_depth}) exceeded for {dot_path}")

    valid_key(key)
    return key, value


def valid_dict(dct):
    remap(dct, visit=visit, enter=enter)


def send_email(to, subject, template):
    sns_client.publish(TopicArn=to, Message=template, Subject=subject)


def get_collections(db):
    """get list of collections in DB"""
    conn = db.app.extensions["mongoengine"][db]["conn"]
    dbname = db.app.config.get("MPCONTRIBS_DB")
    return conn[dbname].list_collection_names()


def get_resource_as_string(name, charset="utf-8"):
    """http://flask.pocoo.org/snippets/77/"""
    with current_app.open_resource(name) as f:
        return f.read().decode(charset)


def create_app():
    """create flask app"""
    app = Flask(__name__)
    app.config.from_pyfile("config.py", silent=True)
    logger.warning("database: " + app.config["MPCONTRIBS_DB"])
    app.config["USTS"] = URLSafeTimedSerializer(app.secret_key)
    app.jinja_env.globals["get_resource_as_string"] = get_resource_as_string
    app.jinja_env.lstrip_blocks = True
    app.jinja_env.trim_blocks = True

    if app.config.get("DEBUG"):
        from flask_cors import CORS

        CORS(app)  # enable for development (allow localhost)

    Compress(app)
    Logging(app)
    Marshmallow(app)
    MongoEngine(app)
    Swagger(app, template=app.config.get("TEMPLATE"))
    # NOTE: hard-code to avoid pre-generating for new deployment
    # collections = get_collections(db)
    collections = [
        "projects",
        "contributions",
        "tables",
        "structures",
        "notebooks",
    ]

    for collection in collections:
        module_path = ".".join(["mpcontribs", "api", collection, "views"])
        try:
            module = import_module(module_path)
        except ModuleNotFoundError as ex:
            logger.warning(f"API module {module_path}: {ex}")
            continue

        try:
            blueprint = getattr(module, collection)
            app.register_blueprint(blueprint, url_prefix="/" + collection)
            klass = getattr(module, collection.capitalize() + "View")
            register_class(app, klass, name=collection)
            logger.warning(f"{collection} registered")
        except AttributeError as ex:
            logger.warning(f"Failed to register {module_path}: {collection} {ex}")

    ## TODO discover user-contributed views automatically
    ## TODO revive redox_thermo_csp again
    ## only load for main deployment
    # if os.environ.get("API_PORT", "5000") == "5000":
    #    collection = "redox_thermo_csp"
    #    module_path = ".".join(["mpcontribs", "api", collection, "views"])
    #    try:
    #        module = import_module(module_path)
    #        blueprint = getattr(module, collection)
    #        app.register_blueprint(blueprint, url_prefix="/" + collection)
    #        logger.warning(f"{collection} registered")
    #    except ModuleNotFoundError as ex:
    #        logger.warning(f"API module {module_path}: {ex}")

    app.register_blueprint(sse, url_prefix="/stream")
    # TODO add healthcheck view/url
    logger.warning("app created.")
    return app
