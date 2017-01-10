# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from pprint import pprint
import django
from django.db import connection
from django.db import models
from django.forms.models import model_to_dict

logger = logging.getLogger(__name__)

class SoftDeleteManager(models.Manager):

    def get_query_set(self):
        return super(SoftDeleteManager, self).get_query_set().filter(deleted=False)

    def all_with_deleted(self):
        return super(SoftDeleteManager, self).get_query_set()

    def deleted_set(self):
        return super(SoftDeleteManager, self).get_query_set().filter(deleted=True)

class DataAccessObject(object):

    def __init__(self, model):
        self.model = model
        self.objects = model.objects

    def find_one_by(self, field, value):
        criteria = {}
        criteria[field] = value
        return self.find_one(**criteria)

    def find_one(self, **criteria):
        try:
            result = self.objects.filter(**criteria)[:1]
            if len(result):
                return result[0]
            return None
        except self.model.DoesNotExist:
            return None

    def find_one_or_create(self, **criteria):
        (obj, created) = self.objects.get_or_create(defaults=criteria, **criteria)
        return (obj, created)

    def get_or_create(self, defaults={}, **criteria):
        (obj, created) = self.objects.get_or_create(defaults=defaults, **criteria)
        return (obj, created)

    def create_or_update(self, defaults={}, **criteria):
        (obj, created) = self.objects.get_or_create(defaults=defaults, **criteria)
        if not created:
            obj.__dict__.update(defaults)
            obj.save()
        return obj

    def find_many_by(self, field, value):
        criteria = {}
        criteria[field] = value
        return self.find_many(**criteria)

    def find_many(self, **criteria):
        return self.objects.filter(**criteria)

    def find_all(self):
        return self.objects.all()

    def id_or_object(self, klass, value):
        if isinstance(value, klass):
            return value
        else:
            try:
                return int(value)
            except ValueError:
                raise AttributeError('Mandatory word attribute should be Word or numeric')

    def create(self, **attributes):
        return self.objects.create(**attributes)

    def delete(self, **criteria):
        return self.objects.filter(**criteria).delete()

    def count(self, **criteria):
        return self.objects.filter(**criteria).count()

    def new(self):
        return self.model()


class RegisterDAO(object):
    """
    Decorator that turns class into object callable from command line.
    Usage:
        @RegisterModel(DjangoModel)
        class TestModel(object):
            ...
    """

    def __init__(self, model_class, name=None):
        self.__model_class = model_class
        self.__name = name

    def __call__(self, dao_class=DataAccessObject):
        self.__dao_class = dao_class
        model.register(self.__model_class, self.__dao_class, self.__name)

        return self.__dao_class

class ModelFactory(object):
    """
    Wstępnie inicjalizuje i zwraca obiekt modelu.
    """
    cache = {}

    models = {}

    def register(self, object_class, model_class=DataAccessObject, name=None):
        if not name:
            name = object_class.__name__
        name = name.lower()
        self.models[name] = (object_class, model_class)

    def get(self, name):
        """ Returns instance of model object specified by name parameter """

        name = name.lower()

        if name in self.cache:
            return self.cache[name]

        if name in self.models:
            object_class, model_class = self.models[name]
            model = self.__create_model(object_class, model_class)
        else:
            raise AttributeError(u'No such model: %s' % (name, ))

        self.cache[name] = model

        return model

    def __create_model(self, object_class, model_class):
        model = model_class(object_class)

        return model

    def __getattr__(self, name):
        return self.get(name)

    def to_dict(self, obj, fields=[], exclude=[], related=[]):
        if isinstance(obj, (models.query.QuerySet, list, tuple)):
            result = []
            for entry in obj:
                if fields or exclude:
                    record = model_to_json(entry, fields=fields, exclude=exclude, related=related)
                else:
                    record = model_to_json(entry, related=related)
                result.append(record)
            return result
        elif isinstance(obj, models.Model):
            if fields or exclude:
                return model_to_json(obj, fields=fields, exclude=exclude, related=related)
            else:
                return model_to_json(obj, related=related)
        elif isinstance(obj, dict):
            return obj
        else:
            raise AttributeError('Wrong type pased to to_dict method: %s' % (type(obj), ))

def model_to_json(obj, fields=None, exclude=None, related=[]):

    result = {}
    # pprint( dir(obj._meta))
    # print'------------------------------'
    # pprint( dir(obj))
    # print obj._meta.get_all_field_names()
    # print obj._meta.fields
    # print obj._meta._field_cache
    for field in obj._meta.fields:
        key = field.name
        # key = field
        # print '->'
        # print '++++'
        # value = obj.__getattribute__(key)

        # if isinstance(value, datetime):
        if isinstance(field, django.db.models.fields.DateTimeField):
            value = getattr(obj, key)
            if value and not isinstance(value, str):
                value = value.strftime("%Y-%m-%d %H:%M:%S")
        # if isinstance(value, models.Model):
        elif isinstance(field, django.db.models.fields.related.ForeignKey):
            if key in related:
                value = getattr(obj, key)
                if value:
                    value = model_to_json(value)
                    result[key + '_id'] = value['id']
                else:
                    value = None
                    result[key + '_id'] = None
            else:
                continue
        else:
            value = getattr(obj, key)

        if fields:
            if key in fields:
                result[key] = value
        else:
            result[key] = value

        if exclude:
            if key in exclude:
                del result[key]

    return result

def map_collection(collection, key):
    return dict([(isinstance(entry, dict) and entry[key] or getattr(entry, key), entry) for entry in collection])

def group_collection(collection, key):
    result = {}
    for entry in collection:
        group_id = isinstance(entry, dict) and entry[key] or getattr(entry, key)
        if group_id not in result.keys():
            result[group_id] = []
        result[group_id].append(entry)

    return result

def debug_sql_queries():
    time = 0.0
    logger.debug('*******************************')
    for q in connection.queries:
        time += float(q['time'])
        logger.debug("%s  %f" % (q['sql'], float(q['time'])))

    logger.debug('SQL queries: %d    time: %f' % (len(connection.queries), time))
    logger.debug('*******************************')

model = ModelFactory()
DAO = RegisterDAO