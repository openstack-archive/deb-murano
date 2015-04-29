#    Copyright (c) 2014 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo.config import cfg
from oslo.db.sqlalchemy import utils
import sqlalchemy as sa
from sqlalchemy import or_
from sqlalchemy.orm import attributes
# TODO(ruhe) use exception declared in openstack/common/db
from webob import exc

from murano.db import models
from murano.db import session as db_session
from murano.common.i18n import _, _LW
from murano.openstack.common import log as logging

CONF = cfg.CONF

SEARCH_MAPPING = {'fqn': 'fully_qualified_name',
                  'name': 'name',
                  'created': 'created'
                  }

LOG = logging.getLogger(__name__)


def _package_get(package_id_or_name, session):
    # TODO(sjmc7): update openstack/common and pull in
    # uuidutils, check that package_id_or_name resembles a
    # UUID before trying to treat it as one
    package = session.query(models.Package).get(package_id_or_name)
    if not package:
        # Try using the FQN name instead. Since FQNs right now are unique,
        # don't need to do any logic to figure out if we have the right one.
        # # TODO(sjmc7): Revisit for precedence rules.
        #  Heat does this in nicer way, giving each stack an unambiguous ID of
        # stack_name/id and redirecting to it in the API. We need to do some
        # reworking for precedence rules later, so maybe take a look at this
        package = session.query(models.Package).filter_by(
            fully_qualified_name=package_id_or_name
        ).first()

    if not package:
        msg = _("Package id or name '{0}' not found").\
            format(package_id_or_name)
        LOG.error(msg)
        raise exc.HTTPNotFound(explanation=msg)

    return package


def _authorize_package(package, context, allow_public=False):

    if package.owner_id != context.tenant:
        if not allow_public:
            msg = _("Package '{0}' is not owned by "
                    "tenant '{1}'").format(package.id, context.tenant)
            LOG.error(msg)
            raise exc.HTTPForbidden(explanation=msg)
        if not package.is_public:
            msg = _("Package '{0}' is not public and not owned by "
                    "tenant '{1}' ").format(package.id, context.tenant)
            LOG.error(msg)
            raise exc.HTTPForbidden(explanation=msg)


def package_get(package_id_or_name, context):
    """Return package details
       :param package_id: ID or name of a package, string
       :returns: detailed information about package, dict
    """
    session = db_session.get_session()
    package = _package_get(package_id_or_name, session)
    if not context.is_admin:
        _authorize_package(package, context, allow_public=True)
    return package


def _get_categories(category_names, session=None):
    """Return existing category objects or raise an exception.

       :param category_names: name of categories
                              to associate with package, list
       :returns: list of Category objects to associate with package, list
    """
    if session is None:
        session = db_session.get_session()
    categories = []
    for ctg_name in category_names:
        ctg_obj = session.query(models.Category).filter_by(
            name=ctg_name).first()
        if not ctg_obj:
            msg = _("Category '{name}' doesn't exist").format(name=ctg_name)
            LOG.error(msg)
            # it's not allowed to specify non-existent categories
            raise exc.HTTPBadRequest(explanation=msg)

        categories.append(ctg_obj)
    return categories


def _get_tags(tag_names, session=None):
    """Return existing tags object or create new ones
       :param tag_names: name of tags to associate with package, list
       :returns: list of Tag objects to associate with package, list
    """
    if session is None:
        session = db_session.get_session()
    tags = []
    for tag_name in tag_names:
        tag_obj = session.query(models.Tag).filter_by(name=tag_name).first()
        if tag_obj:
            tags.append(tag_obj)
        else:
            tag_record = models.Tag(name=tag_name)
            tags.append(tag_record)
    return tags


def _get_class_definitions(class_names, session=None):
    classes = []
    for name in class_names:
        class_record = models.Class(name=name)
        classes.append(class_record)
    return classes


def _do_replace(package, change):
    path = change['path'][0]
    value = change['value']
    calculate = {'categories': _get_categories,
                 'tags': _get_tags}
    if path in ('categories', 'tags'):
        existing_items = getattr(package, path)

        duplicates = list(set(i.name for i in existing_items) & set(value))
        unique_values = [x for x in value if x not in duplicates]
        items_to_replace = calculate[path](unique_values)

        # NOTE(efedorova): Replacing duplicate entities is not allowed,
        # so need to remove anything, but duplicates
        # and append everything but duplicates
        for item in list(existing_items):
            if item.name not in duplicates:
                existing_items.remove(item)

        existing_items.extend(items_to_replace)
    else:
        setattr(package, path, value)

    return package


def _do_add(package, change):
    # Only categories and tags support addition
    path = change['path'][0]
    value = change['value']

    calculate = {'categories': _get_categories,
                 'tags': _get_tags}
    items_to_add = calculate[path](value)
    for item in items_to_add:
        try:
            getattr(package, path).append(item)
        except AssertionError:
            msg = _LW('One of the specified {0} is already '
                      'associated with a package. Doing nothing.')
            LOG.warning(msg.format(path))
    return package


def _do_remove(package, change):
    # Only categories and tags support removal
    def find(seq, predicate):
        for elt in seq:
            if predicate(elt):
                return elt

    path = change['path'][0]
    values = change['value']

    current_values = getattr(package, path)
    for value in values:
        if value not in [i.name for i in current_values]:
            msg = _("Value '{0}' of property '{1}' "
                    "does not exist.").format(value, path)
            LOG.error(msg)
            raise exc.HTTPNotFound(explanation=msg)
        item_to_remove = find(current_values, lambda i: i.name == value)
        current_values.remove(item_to_remove)
    return package


def _get_packages_for_category(session, category_id):
    """Return detailed list of packages, belonging to the provided category
    :param session:
    :param category_id:
    :return: list of dictionaries, containing id, name and package frn
    """
    pkg = models.Package
    packages = (session.query(pkg.id, pkg.name, pkg.fully_qualified_name)
                .filter(pkg.categories
                        .any(models.Category.id == category_id))
                .all())

    result_packages = []
    for package in packages:
        id, name, fqn = package
        result_packages.append({'id': id,
                                'name': name,
                                'fully_qualified_name': fqn})
    return result_packages


def package_update(pkg_id_or_name, changes, context):
    """Update package information
       :param changes: parameters to update
       :returns: detailed information about new package, dict
    """

    operation_methods = {'add': _do_add,
                         'replace': _do_replace,
                         'remove': _do_remove}
    session = db_session.get_session()
    with session.begin():
        pkg = _package_get(pkg_id_or_name, session)
        was_private = not pkg.is_public
        if not context.is_admin:
            _authorize_package(pkg, context)

        for change in changes:
            pkg = operation_methods[change['op']](pkg, change)
        became_public = pkg.is_public
        class_names = [clazz.name for clazz in pkg.class_definitions]
        if was_private and became_public:
            with db_session.get_lock("public_packages", session):
                _check_for_existing_classes(session, class_names, None,
                                            check_public=True,
                                            ignore_package_with_id=pkg.id)
                _check_for_public_packages_with_fqn(session,
                                                    pkg.fully_qualified_name,
                                                    pkg.id)
        session.add(pkg)
    return pkg


def package_search(filters, context, limit=None):
    """Search packages with different filters
      * Admin is allowed to browse all the packages
      * Regular user is allowed to browse all packages belongs to user tenant
        and all other packages marked is_public.
        Also all packages should be enabled.
      * Use marker (inside filters param) and limit for pagination:
        The typical pattern of limit and marker is to make an initial limited
        request and then to use the ID of the last package from the response
        as the marker parameter in a subsequent limited request.
    """
    session = db_session.get_session()
    pkg = models.Package

    # If the packages search specifies the inclusion of disabled packages,
    # we handle this differently for admins vs non-admins:
    # For admins: *don't* require pkg.enabled == True (no changes to query)
    # For non-admins: add an OR-condition to filter for packages that are owned
    #                 by the tenant in the current context
    # Otherwise: in all other cases, we return only enabled packages
    if filters.get('include_disabled', '').lower() == 'true':
        include_disabled = True
    else:
        include_disabled = False

    if context.is_admin:
        if not include_disabled:
            # NOTE(efedorova): is needed for SA 0.7.9, but could be done
            # simpler in SA 0.8. See http://goo.gl/9stlKu for a details
            query = session.query(pkg).filter(pkg.__table__.c.enabled)
        else:
            query = session.query(pkg)
    elif filters.get('owned', '').lower() == 'true':
        if not include_disabled:
            query = session.query(pkg).filter(
                (pkg.owner_id == context.tenant) & pkg.enabled
            )
        else:
            query = session.query(pkg).filter(pkg.owner_id == context.tenant)
    else:
        if not include_disabled:
            query = session.query(pkg).filter(
                or_((pkg.is_public & pkg.enabled),
                    ((pkg.owner_id == context.tenant) & pkg.enabled))
            )
        else:
            query = session.query(pkg).filter(
                or_((pkg.is_public & pkg.enabled),
                    pkg.owner_id == context.tenant)
            )

    if 'type' in filters.keys():
        query = query.filter(pkg.type == filters['type'].title())

    if 'category' in filters.keys():
        query = query.filter(pkg.categories.any(
            models.Category.name.in_(filters['category'])))
    if 'tag' in filters.keys():
        query = query.filter(pkg.tags.any(
            models.Tag.name.in_(filters['tag'])))
    if 'class_name' in filters.keys():
        query = query.filter(pkg.class_definitions.any(
            models.Class.name == filters['class_name']))
    if 'fqn' in filters.keys():
        query = query.filter(pkg.fully_qualified_name == filters['fqn'])

    if 'search' in filters.keys():
        fk_fields = {'categories': 'Category',
                     'tags': 'Tag',
                     'class_definitions': 'Class'}
        conditions = []

        for attr in dir(pkg):
            if attr.startswith('_'):
                continue
            if isinstance(getattr(pkg, attr),
                          attributes.InstrumentedAttribute):
                search_str = filters['search']
                for delim in ',;':
                    search_str = search_str.replace(delim, ' ')
                for key_word in search_str.split():
                    _word = '%{value}%'.format(value=key_word)
                    if attr in fk_fields.keys():
                        condition = getattr(pkg, attr).any(
                            getattr(models, fk_fields[attr]).name.like(_word))
                        conditions.append(condition)
                    elif isinstance(getattr(pkg, attr)
                                    .property.columns[0].type, sa.String):
                        conditions.append(getattr(pkg, attr).like(_word))
        query = query.filter(or_(*conditions))

    sort_keys = [SEARCH_MAPPING[sort_key] for sort_key in
                 filters.get('order_by', []) or ['name']]
    marker = filters.get('marker')
    # TODO(btully): sort_dir is always None - not getting passed as a filter?
    sort_dir = filters.get('sort_dir')
    if marker is not None:  # set marker to real object instead of its id
        marker = _package_get(marker, session)
    query = utils.paginate_query(
        query, pkg, limit, sort_keys, marker, sort_dir)

    return query.all()


def package_upload(values, tenant_id):
    """Upload a package with new application
       :param values: parameters describing the new package
       :returns: detailed information about new package, dict
    """
    session = db_session.get_session()
    package = models.Package()

    composite_attr_to_func = {'categories': _get_categories,
                              'tags': _get_tags,
                              'class_definitions': _get_class_definitions}
    is_public = values.get('is_public', False)

    if is_public:
        public_lock = db_session.get_lock("public_packages", session)
    else:
        public_lock = None
    tenant_lock = db_session.get_lock("classes_of_" + tenant_id, session)
    try:
        _check_for_existing_classes(session, values.get('class_definitions'),
                                    tenant_id, check_public=is_public)
        if is_public:
            _check_for_public_packages_with_fqn(
                session,
                values.get('fully_qualified_name'))
        for attr, func in composite_attr_to_func.iteritems():
            if values.get(attr):
                result = func(values[attr], session)
                setattr(package, attr, result)
                del values[attr]
        package.update(values)
        package.owner_id = tenant_id
        package.save(session)
        tenant_lock.commit()
        if public_lock is not None:
            public_lock.commit()
    except Exception:
        tenant_lock.rollback()
        if public_lock is not None:
            public_lock.rollback()
        raise

    return package


def package_delete(package_id_or_name, context):
    """Delete a package by name or by ID."""
    session = db_session.get_session()

    with session.begin():
        package = _package_get(package_id_or_name, session)
        if not context.is_admin and package.owner_id != context.tenant:
            raise exc.HTTPForbidden(
                explanation='Package is not owned by the'
                            ' tenant "{0}"'.format(context.tenant))
        session.delete(package)


def category_get(category_id, session=None, packages=False):
    """Return category details
       :param category_id: ID of a category, string
       :returns: detailed information about category, dict
    """
    if not session:
        session = db_session.get_session()

    category = session.query(models.Category).get(category_id)
    if not category:
        msg = _("Category id or '{0}' not found").format(category_id)
        LOG.error(msg)
        raise exc.HTTPNotFound(msg)
    if packages:
        category.packages = _get_packages_for_category(session, category_id)
    return category


def categories_list():
    session = db_session.get_session()
    return session.query(models.Category).all()


def category_get_names():
    session = db_session.get_session()
    categories = []
    for row in session.query(models.Category.name).all():
        for name in row:
            categories.append(name)
    return categories


def category_add(category_name):
    session = db_session.get_session()
    category = models.Category()

    with session.begin():
        category.update({'name': category_name})
        # NOTE(kzaitsev) update package_count, so we can safely access from
        # outside the session
        category.package_count = 0
        category.save(session)

    return category


def category_delete(category_id):
    """Delete a category by ID."""
    session = db_session.get_session()

    with session.begin():
        category = session.query(models.Category).get(category_id)
        if not category:
            msg = _("Category id '{0}' not found").format(category_id)
            LOG.error(msg)
            raise exc.HTTPNotFound(msg)
        session.delete(category)


def _check_for_existing_classes(session, class_names, tenant_id,
                                check_public=False,
                                ignore_package_with_id=None):
    if not class_names:
        return
    q = session.query(models.Class.name).filter(
        models.Class.name.in_(class_names))
    private_filter = None
    public_filter = None
    predicate = None
    if tenant_id is not None:
        private_filter = models.Class.package.has(
            models.Package.owner_id == tenant_id)
    if check_public:
        public_filter = models.Class.package.has(
            models.Package.is_public)
    if private_filter is not None and public_filter is not None:
        predicate = sa.or_(private_filter, public_filter)
    elif private_filter is not None:
        predicate = private_filter
    elif public_filter is not None:
        predicate = public_filter
    if predicate is not None:
        q = q.filter(predicate)
    if ignore_package_with_id is not None:
        q = q.filter(models.Class.package_id != ignore_package_with_id)
    if q.first() is not None:
        msg = _('Class with the same full name is already '
                'registered in the visibility scope')
        LOG.error(msg)
        raise exc.HTTPConflict(msg)


def _check_for_public_packages_with_fqn(session, fqn,
                                        ignore_package_with_id=None):
    q = session.query(models.Package.id).\
        filter(models.Package.is_public).\
        filter(models.Package.fully_qualified_name == fqn)
    if ignore_package_with_id is not None:
        q = q.filter(models.Package.id != ignore_package_with_id)
    if q.first() is not None:
        msg = _('Package with the same Name is already made public')
        LOG.error(msg)
        raise exc.HTTPConflict(msg)
