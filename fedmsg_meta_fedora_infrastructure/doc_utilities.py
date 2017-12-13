""" Code to generate doc/topics.rst during 'sphinx-build'.

This code:

- Uses :mod:`nose` to find all the fedmsg.meta unittests.
- Extracts all the metadata and docstrings from those tests.
- Uses all that to generate a giant .rst document of all the fedmsg
  topics and what they are about with example messages.

"""

import nose
import pprint
import textwrap
import uuid

import mako.template
import six

from fedmsg.tests.test_meta import Unspecified

header = """
List of Message Topics
======================

.. DO NOT EDIT THIS DOCUMENT.

.. It is autogenerated from fedmsg_meta_fedora_infrastructure/doc_utilities.py

This document lists all the topics coming out the Fedora
Infrastructure fedmsg bus.  Example messages are included
as well as descriptions and sample output from ``fedmsg.meta``.

.. note:: All topics from Fedora Infrastructure are prefixed with
   ``org.fedoraproject.prod.``, but the :term:`topic_prefix` is omitted here
   for brevity.  For instance, the item listed as ``git.branch`` will
   actually be broadcast as ``org.fedoraproject.prod.git.branch``.

.. note:: Message bodies can contain some useful information, but be wary.
   We have done as good a job as we can *securing* fedmsg, but it is still
   a new system.  If you receive a message from pkgdb claiming that "ralph"
   is the new owner of the kernel, you should still *check* with the *actual*
   pkgdb service that this is the case.  Write code against fedmsg messages
   as a tip, but always check the authoritative source before taking any
   programmatic action.

"""

metadata_template = mako.template.Template("""
The example message above, when passed to various routines in the
:mod:`fedmsg.meta` module, will produce the following outputs:

+-----------------------------------------+${'-' * (longest + 2)}+
| :func:`fedmsg.meta.msg2title`           | ${str(title).ljust(longest)} |
+-----------------------------------------+${'-' * (longest + 2)}+
| :func:`fedmsg.meta.msg2subtitle`        | ${str(subtitle).ljust(longest)} |
+-----------------------------------------+${'-' * (longest + 2)}+
| :func:`fedmsg.meta.msg2link`            | ${str(link).ljust(longest)} |
+-----------------------------------------+${'-' * (longest + 2)}+
| :func:`fedmsg.meta.msg2agent`           | ${str(agent).ljust(longest)} |
+-----------------------------------------+${'-' * (longest + 2)}+
| :func:`fedmsg.meta.msg2usernames`       | ${repr(usernames).ljust(longest)} |
+-----------------------------------------+${'-' * (longest + 2)}+
| :func:`fedmsg.meta.msg2packages`        | ${repr(packages).ljust(longest)} |
+-----------------------------------------+${'-' * (longest + 2)}+
| :func:`fedmsg.meta.msg2objects`         | ${repr(objects).ljust(longest)} |
+-----------------------------------------+${'-' * (longest + 2)}+
| :func:`fedmsg.meta.msg2icon`            | ${str(icon_inline).ljust(longest)} |
+-----------------------------------------+${'-' * (longest + 2)}+
| :func:`fedmsg.meta.msg2secondary_icon`  | ${str(secondary_icon_inline).ljust(longest)} |
+-----------------------------------------+${'-' * (longest + 2)}+

% if not icon is Unspecified:
.. ${icon_inline} image:: ${icon}
   :height: 32px
   :width: 32px
% endif
% if not secondary_icon is Unspecified:
.. ${secondary_icon_inline} image:: ${secondary_icon}
   :height: 32px
   :width: 32px
% endif

""")

outfile = None


def write(fname, s=''):
    global outfile
    if not outfile:
        outfile = open(fname, 'w')

    outfile.write(s + '\n')


def datagrepper_link(topic):
    suffix = '.'.join(topic.split('.')[3:])
    category = topic.split('.')[3]
    base_url = 'https://apps.fedoraproject.org/datagrepper/raw'
    topic_link = base_url + '?topic=%s' % topic
    category_link = base_url + '?category=%s' % category
    tmpl = (
        "You can view the history of `messages with the %s topic <%s>`_ "
        "or `all %s messages <%s>`_ in datagrepper."
    )
    return tmpl % (suffix, topic_link, category, category_link)


def load_classes(module):
    return list(nose.loader.defaultTestLoader().loadTestsFromModule(module))


def make_topics_doc(output_dir):

    fname = output_dir + "/topics.rst"

    global outfile
    import fedmsg_meta_fedora_infrastructure.tests as source_module
    test_classes = load_classes(source_module)

    # TODO -- get the logger and announce messages
    #import fedmsg
    #filename = fedmsg.__file__
    #folder = os.path.sep + os.path.join(*filename.split('/')[:-1])
    #test_classes = load_classes(folder)

    # Strip out the conglomerator tests which are more complicated.
    test_classes = [cls for cls in test_classes if hasattr(cls.context, 'msg')]

    write(fname, header)

    for cls in test_classes:
        if not cls.context.msg is Unspecified:
            # Adjust {stg,dev} to prod.
            cls.context.msg['topic'] = cls.context.msg['topic']\
                .replace('.stg.', '.prod.')\
                .replace('.dev.', '.prod.')
            cls.context.expected_title = cls.context.expected_title\
                .replace('.stg.', '.prod.')\
                .replace('.dev.', '.prod.')

            topic = '.'.join(cls.context.msg['topic'].split('.')[3:])
            cls.__topic = topic
        else:
            cls.__topic = None

    comparator = lambda a, b: cmp(a.__topic, b.__topic)
    test_classes = sorted(test_classes, comparator)

    seen = []
    for cls in test_classes:
        if not cls.context.msg is Unspecified:
            topic = cls.__topic

            # Ignore tests that check old messages.
            if 'Legacy' in cls.context.__name__:
                continue

            # You can also exclude a test from the docs with nodoc = True
            if getattr(cls.context, 'nodoc', False) is True:
                continue

            modname = topic.split('.')[0]
            if not modname in seen:
                seen.append(modname)
                write(fname, modname)
                write(fname, "-" * len(modname))
                write(fname)

            write(fname, topic)
            write(fname, "~" * len(topic))
            write(fname)

            # I would use __doc__ here, but something that nose is doing is
            # stripping the __doc__ from my original unit tests.  Instead,
            # we'll use our own 'doc' attribute which is a little clumsy.
            if getattr(cls.context, 'doc', None):
                write(fname, textwrap.dedent("    " + cls.context.doc.strip()))
                write(fname)

            write(fname, datagrepper_link(cls.context.msg['topic']))
            write(fname)

            write(fname, ".. code-block:: python")
            write(fname, '\n    ' + pprint.pformat(cls.context.msg, indent=2)
                  .replace('\n', '\n    '))
            write(fname)

            # This is a unique id per entry so we don't collide image tags
            uid = str(uuid.uuid4())
            icon_inline = Unspecified
            secondary_icon_inline = Unspecified
            if not cls.context.expected_icon is Unspecified:
                icon_inline = "|%s-icon|" % uid
            if not cls.context.expected_secondary_icon is Unspecified:
                secondary_icon_inline = "|%s-secondary_icon|" % uid

            # A bunch of data for the template.
            kwargs = dict(
                link=cls.context.expected_link,
                title=cls.context.expected_title,
                subtitle=cls.context.expected_subti,
                usernames=cls.context.expected_usernames,
                agent=cls.context.expected_agent,
                packages=cls.context.expected_packages,
                objects=cls.context.expected_objects,
                icon_inline=icon_inline,
                secondary_icon_inline=secondary_icon_inline,
            )

            def length(value):
                """ Find longest string so we can pad our tables adequately """
                if isinstance(value, six.string_types):
                    return len(value)
                return len(repr(value))
            longest = max([length(value) for value in kwargs.values()])

            write(fname, metadata_template.render(
                icon=cls.context.expected_icon,
                secondary_icon=cls.context.expected_secondary_icon,
                Unspecified=Unspecified,
                longest=longest,
                **kwargs
            ))
            write(fname)

    outfile.close()

if __name__ == '__main__':
    make_topics_doc()
