# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
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

"""
SQLAlchemy models for nova data
"""

import logging

from sqlalchemy.orm import relationship, backref, validates, exc
from sqlalchemy import Table, Column, Integer, String
from sqlalchemy import MetaData, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base

from nova.db.sqlalchemy.session import managed_session
from nova import auth
from nova import exception
from nova import flags

FLAGS=flags.FLAGS

Base = declarative_base()

class NovaBase(object):
    __table_args__ = {'mysql_engine':'InnoDB'}
    __table_initialized__ = False
    __prefix__ = 'none'
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    deleted = Column(Boolean, default=False)

    @classmethod
    def all(cls, session=None):
        if session:
            return session.query(cls) \
                          .filter_by(deleted=False) \
                          .all()
        else:
            with managed_session() as s:
                return cls.all(session=s)

    @classmethod
    def count(cls, session=None):
        if session:
            return session.query(cls) \
                          .filter_by(deleted=False) \
                          .count()
        else:
            with managed_session() as s:
                return cls.count(session=s)

    @classmethod
    def find(cls, obj_id, session=None):
        if session:
            try:
                return session.query(cls) \
                              .filter_by(id=obj_id) \
                              .filter_by(deleted=False) \
                              .one()
            except exc.NoResultFound:
                raise exception.NotFound("No model for id %s" % obj_id)
        else:
            with managed_session() as s:
                return cls.find(obj_id, session=s)

    @classmethod
    def find_by_str(cls, str_id, session=None):
        id = int(str_id.rpartition('-')[2])
        return cls.find(id, session=session)

    @property
    def str_id(self):
        return "%s-%s" % (self.__prefix__, self.id)

    def save(self, session=None):
        if session:
            session.add(self)
            session.flush()
        else:
            with managed_session() as s:
                self.save(session=s)

    def delete(self, session=None):
        self.deleted = True
        self.save(session=session)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)


class Image(Base, NovaBase):
    __tablename__ = 'images'
    __prefix__ = 'ami'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))#, ForeignKey('users.id'), nullable=False)
    project_id = Column(String(255))#, ForeignKey('projects.id'), nullable=False)
    image_type = Column(String(255))
    public = Column(Boolean, default=False)
    state = Column(String(255))
    location = Column(String(255))
    arch = Column(String(255))
    default_kernel_id = Column(String(255))
    default_ramdisk_id = Column(String(255))

    @validates('image_type')
    def validate_image_type(self, key, image_type):
        assert(image_type in ['machine', 'kernel', 'ramdisk', 'raw'])

    @validates('state')
    def validate_state(self, key, state):
        assert(state in ['available', 'pending', 'disabled'])

    @validates('default_kernel_id')
    def validate_kernel_id(self, key, val):
        if val != 'machine':
            assert(val is None)

    @validates('default_ramdisk_id')
    def validate_ramdisk_id(self, key, val):
        if val != 'machine':
            assert(val is None)


class PhysicalNode(Base, NovaBase):
    __tablename__ = 'physical_nodes'
    id = Column(String(255), primary_key=True)

class Daemon(Base, NovaBase):
    __tablename__ = 'daemons'
    id = Column(Integer, primary_key=True)
    node_name = Column(String(255))  #, ForeignKey('physical_node.id'))
    binary = Column(String(255))
    report_count = Column(Integer, nullable=False, default=0)

    @classmethod
    def find_by_args(cls, session, node_name, binary):
        try:
            return session.query(cls) \
                          .filter_by(node_name=node_name) \
                          .filter_by(binary=binary) \
                          .filter_by(deleted=False) \
                          .one()
        except exc.NoResultFound:
            raise exception.NotFound("No model for %s, %s" % (node_name,
                                                              binary))


class Instance(Base, NovaBase):
    __tablename__ = 'instances'
    __prefix__ = 'i'
    id = Column(Integer, primary_key=True)

    user_id = Column(String(255)) #, ForeignKey('users.id'), nullable=False)
    project_id = Column(String(255)) #, ForeignKey('projects.id'))

    @property
    def user(self):
        return auth.manager.AuthManager().get_user(self.user_id)

    @property
    def project(self):
        return auth.manager.AuthManager().get_project(self.project_id)

    # TODO(vish): make this opaque somehow
    @property
    def name(self):
        return self.str_id


    image_id = Column(Integer, ForeignKey('images.id'), nullable=True)
    kernel_id = Column(Integer, ForeignKey('images.id'), nullable=True)
    ramdisk_id = Column(Integer, ForeignKey('images.id'), nullable=True)

    launch_index = Column(Integer)
    key_name = Column(String(255))
    key_data = Column(Text)
    security_group = Column(String(255))

    state = Column(Integer)
    state_description = Column(String(255))

    hostname = Column(String(255))
    node_name = Column(String(255))  #, ForeignKey('physical_node.id'))

    instance_type = Column(Integer)

    user_data = Column(Text)

    reservation_id = Column(String(255))
    mac_address = Column(String(255))

    def set_state(self, state_code, state_description=None):
        # TODO(devcamcar): Move this out of models and into api
        from nova.compute import power_state
        self.state = state_code
        if not state_description:
            state_description = power_state.name(state_code)
        self.state_description = state_description
        self.save()

#    ramdisk = relationship(Ramdisk, backref=backref('instances', order_by=id))
#    kernel = relationship(Kernel, backref=backref('instances', order_by=id))
#    project = relationship(Project, backref=backref('instances', order_by=id))

#TODO - see Ewan's email about state improvements
    # vmstate_state = running, halted, suspended, paused
    # power_state = what we have
    # task_state = transitory and may trigger power state transition

    #@validates('state')
    #def validate_state(self, key, state):
    #    assert(state in ['nostate', 'running', 'blocked', 'paused', 'shutdown', 'shutoff', 'crashed'])

class Volume(Base, NovaBase):
    __tablename__ = 'volumes'
    __prefix__ = 'vol'
    id = Column(Integer, primary_key=True)

    user_id = Column(String(255)) #, ForeignKey('users.id'), nullable=False)
    project_id = Column(String(255)) #, ForeignKey('projects.id'))

    node_name = Column(String(255))  #, ForeignKey('physical_node.id'))
    size = Column(Integer)
    availability_zone = Column(String(255)) # TODO(vish) foreign key?
    instance_id = Column(Integer, ForeignKey('instances.id'), nullable=True)
    mountpoint = Column(String(255))
    attach_time = Column(String(255)) # TODO(vish) datetime
    status = Column(String(255)) # TODO(vish) enum?
    attach_status = Column(String(255)) # TODO(vish) enum

class ExportDevice(Base, NovaBase):
    __tablename__ = 'export_devices'
    id = Column(Integer, primary_key=True)
    shelf_id = Column(Integer)
    blade_id = Column(Integer)
    volume_id = Column(Integer, ForeignKey('volumes.id'), nullable=True)
    volume = relationship(Volume, backref=backref('export_device',
                                                  uselist=False))


# TODO(vish): can these both come from the same baseclass?
class FixedIp(Base, NovaBase):
    __tablename__ = 'fixed_ips'
    id = Column(Integer, primary_key=True)
    ip_str = Column(String(255))
    network_id = Column(Integer, ForeignKey('networks.id'), nullable=False)
    instance_id = Column(Integer, ForeignKey('instances.id'), nullable=True)
    instance = relationship(Instance, backref=backref('fixed_ip',
                                                      uselist=False))
    allocated = Column(Boolean, default=False)
    leased = Column(Boolean, default=False)
    reserved = Column(Boolean, default=False)

    @property
    def str_id(self):
        return self.ip_str

    @classmethod
    def find_by_str(cls, session, str_id):
        try:
            return session.query(cls) \
                          .filter_by(ip_str=str_id) \
                          .filter_by(deleted=False) \
                          .one()
        except exc.NoResultFound:
            raise exception.NotFound("No model for ip str %s" % str_id)


class FloatingIp(Base, NovaBase):
    __tablename__ = 'floating_ips'
    id = Column(Integer, primary_key=True)
    ip_str = Column(String(255))
    fixed_ip_id = Column(Integer, ForeignKey('fixed_ips.id'), nullable=True)
    fixed_ip = relationship(FixedIp, backref=backref('floating_ips'))

    project_id = Column(String(255)) #, ForeignKey('projects.id'), nullable=False)
    node_name = Column(String(255))  #, ForeignKey('physical_node.id'))

    @property
    def str_id(self):
        return self.ip_str

    @classmethod
    def find_by_str(cls, session, str_id):
        try:
            return session.query(cls) \
                          .filter_by(ip_str=str_id) \
                          .filter_by(deleted=False) \
                          .one()
        except exc.NoResultFound:
            raise exception.NotFound("No model for ip str %s" % str_id)


class Network(Base, NovaBase):
    __tablename__ = 'networks'
    id = Column(Integer, primary_key=True)

    injected = Column(Boolean, default=False)
    cidr = Column(String(255))
    netmask = Column(String(255))
    bridge = Column(String(255))
    gateway = Column(String(255))
    broadcast = Column(String(255))
    dns = Column(String(255))

    vlan = Column(Integer)
    vpn_public_ip_str = Column(String(255))
    vpn_public_port = Column(Integer)
    vpn_private_ip_str = Column(String(255))
    dhcp_start = Column(String(255))

    project_id = Column(String(255)) #, ForeignKey('projects.id'), nullable=False)
    node_name = Column(String(255))  #, ForeignKey('physical_node.id'))

    fixed_ips = relationship(FixedIp,
                             single_parent=True,
                             backref=backref('network'),
                             cascade='all, delete, delete-orphan')


class NetworkIndex(Base, NovaBase):
    __tablename__ = 'network_indexes'
    id = Column(Integer, primary_key=True)
    index = Column(Integer)
    network_id = Column(Integer, ForeignKey('networks.id'), nullable=True)
    network = relationship(Network, backref=backref('network_index',
                                                    uselist=False))


def register_models():
    from sqlalchemy import create_engine
    models = (Image, PhysicalNode, Daemon, Instance, Volume, ExportDevice,
              FixedIp, FloatingIp, Network, NetworkIndex)
    engine = create_engine(FLAGS.sql_connection, echo=False)
    for model in models:
        model.metadata.create_all(engine)
