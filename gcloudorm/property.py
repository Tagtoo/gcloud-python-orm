import zlib
import cPickle as pickle
import datetime
try:
    import json
except ImportError:
    import simplejson as json


class Property(object):
    def __init__(self, name=None, indexed=True, repeated=False, required=False, default=None, choices=None, validator=None):
        self._name = name
        self._indexed = indexed
        self._repeated = repeated
        self._required = required
        self._default = default
        self._choices = choices
        self._validator = validator

    def __get__(self, instance, owner):
        if self._repeated:
            if self._name not in instance:
                self.__set__(instance, self._default or [])

            return [self.from_base_type(k) for k in instance[self._name]]

        if self._name not in instance:
            self.__set__(instance, self._default)

        return self.from_base_type(instance[self._name])

    def __set__(self, instance, value):
        if self._repeated:
            assert isinstance(value, (tuple, list)), "Repeated property only accept list or tuple"
            value = [self.validate(k) for k in value]
            instance[self._name] = [self.to_base_type(k) for k in value]
        else:
            value = self.validate(value)
            instance[self._name] = self.to_base_type(value)

    def __delete__(self, instance):
        instance.pop(self._name, None)

    def _fix_up(self, cls, name):
        if self._name is None:
            self._name = name

    def validate(self, value):
        assert self._choices is None or value in self._choices
        assert not (self._required and value is not None)
        if value is None:
            return

        self._validate(value)
        if self._validator is not None:
            return self._validator(self, value)

        return value

    def _validate(self, value):
        return value

    def to_base_type(self, value):
        if value is None:
            return value
        return self._to_base_type(value)

    def _to_base_type(self, value):
        return value

    def from_base_type(self, value):
        if value is None:
            return value
        return self._from_base_type(value)

    def _from_base_type(self, value):
        return value

    def _prepare_for_put(self, entity):
        # TODO: check if _required
        pass

    def from_db_value(self, value):
        return self._from_db_value(value)

    def _from_db_value(self, value):
        return value


class BooleanProperty(Property):
    def _validate(self, value):
        assert isinstance(value, bool)
        return value


class IntegerProperty(Property):
    def _validate(self, value):
        assert isinstance(value, (int, long))
        return int(value)


class FloatProperty(Property):
    def _validate(self, value):
        assert isinstance(value, (int, long, float))
        return float(value)


class BlobProperty(Property):
    def __init__(self, name=None, compressed=False, **kwargs):
        kwargs.pop('indexed', None)
        super(BlobProperty, self).__init__(name=name, indexed=False, **kwargs)

        self._compressed = compressed
        assert not (compressed and self._indexed), "BlobProperty %s cannot be compressed and indexed at the same time." % self._name

    def _validate(self, value):
        assert isinstance(value, str), value
        return value

    def _to_base_type(self, value):
        if self._compressed:
            return zlib.compress(value)

        return value

    def _from_base_type(self, value):
        if self._compressed:
            return zlib.decompress(value.z_val)

        return value


class TextProperty(BlobProperty):
    def __init__(self, name=None, indexed=False, **kwargs):
        super(TextProperty, self).__init__(name=name, indexed=indexed, **kwargs)

    def _validate(self, value):
        if isinstance(value, str):
            value = value.decode('utf-8')

        assert isinstance(value, unicode)
        return value

    def _to_base_type(self, value):
        if isinstance(value, str):
            return value.decode('utf-8')

        return value

    def _from_base_type(self, value):
        if isinstance(value, str):
            return unicode(value, 'utf-8')
        elif isinstance(value, unicode):
            return value

    def _from_db_value(self, value):
        if isinstance(value, str):
            return value.decode('utf-8')

        return value


class StringProperty(TextProperty):
    def __init__(self, name=None, indexed=True, **kwargs):
        super(StringProperty, self).__init__(name=name, indexed=indexed, **kwargs)


class PickleProperty(BlobProperty):
    def _to_base_type(self, value):
        return super(PickleProperty, self)._to_base_type(pickle.dumps(value, pickle.HIGHEST_PROTOCOL))

    def _from_base_type(self, value):
        return pickle.loads(super(PickleProperty, self)._from_base_type(value))

    def _validate(self, value):
        return value


class JsonProperty(BlobProperty):
    def __init__(self, name=None, schema=None, **kwargs):
        super(JsonProperty, self).__init__(name, **kwargs)
        self._schema = schema

    def _to_base_type(self, value):
        return super(JsonProperty, self)._to_base_type(json.dumps(value))

    def _from_base_type(self, value):
        return json.loads(super(JsonProperty, self)._from_base_type(value))

    def _validate(self, value):
        return value


class DateTimeProperty(Property):
    def __init__(self, name=None, auto_now_add=False, auto_now=False, **kwargs):
        assert not ((auto_now_add or auto_now) and kwargs.get("repeated", False))
        super(DateTimeProperty, self).__init__(name, **kwargs)
        self._auto_now_add = auto_now_add
        self._auto_now = auto_now

    def _validate(self, value):
        assert isinstance(value, datetime.datetime), value
        return value

    def _now(self):
        return datetime.datetime.utcnow()

    def _prepare_for_put(self, entity):
        v = getattr(entity, self._name)
        if v is None and self._auto_now_add:
            setattr(entity, self._name, self._now())

        if self._auto_now:
            setattr(entity, self._name, self._now())


class DateProperty(DateTimeProperty):
    def _validate(self, value):
        assert isinstance(value, datetime.date)
        return value

    def _to_base_type(self, value):
        return datetime.datetime(value.year, value.month, value.day)

    def _from_base_type(self, value):
        return value.date()

    def _now(self):
        return datetime.datetime.utcnow().date()


class TimeProperty(DateTimeProperty):
    def _validate(self, value):
        assert isinstance(value, datetime.time)
        return value

    def _to_base_type(self, value):
        return datetime.datetime(
            1970, 1, 1,
            value.hour, value.minute, value.second,
            value.microsecond
        )

    def _from_base_type(self, value):
        return value.time()
