#!/usr/bin/python

import logging
import zope
import libxml2
from imgfac.BuildDispatcher import BuildDispatcher
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.CloudDelegate import CloudDelegate
from glance import client as glance_client

def glance_upload(image_filename, creds = {'auth_url': None, 'password': None, 'strategy': 'noauth', 'tenant': None, 'username': None},
                  host = "0.0.0.0", port = "9292", token = None, name = 'Factory Test Image'):

    image_meta = {'container_format': 'bare',
     'disk_format': 'raw',
     'is_public': True,
     'min_disk': 0,
     'min_ram': 0,
     'name': name,
     'properties': {'distro': 'rhel'}}


    c = glance_client.Client(host=host, port=port,
                             auth_tok=token, creds=creds)
    image_data = open(image_filename, "r")
    image_meta = c.add_image(image_meta, image_data)
    image_data.close()
    return image_meta['id']


class OpenStackCloud(object):
    zope.interface.implements(CloudDelegate)

    def __init__(self):
        # Note that we are now missing ( template, target, config_block = None):
        super(OpenStackCloud, self).__init__()
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

    def activity(self, activity):
        # Simple helper function
        # Activity should be a one line human-readable string indicating the task in progress
        # We log it at DEBUG and also set it as the status_detail on our active image
        self.log.debug(activity)
        self.active_image.status_detail['activity'] = activity

    def push_image_to_provider(self, builder, provider, credentials, target, target_image, parameters):
        # Our target_image is already a raw KVM image.  All we need to do is upload to glance
        self.active_image = self.builder.provider_image
        self.openstack_decode_credentials(credentials)

        provider_data = self.get_dynamic_provider_data("openstack-kvm")
        if provider_data is None:
            raise ImageFactoryException("OpenStack KVM instance not found in local configuration file /etc/imagefactory/openstack-kvm.json or as XML or JSON")

        # Image is always here and it is the target_image datafile
        input_image = self.builder.target_image.datafile
        input_image_name = os.path.basename(input_image)

        image_name = 'ImageFactory created image - %s' % (self.builder.provider_image.identifier)
        image_id = glance_upload(input_image, creds = self.credentials_dict, token = self.credentials_token,
                                 hostname=provider_data['glance-host'], port=provider_data['glance-port'])
        
        self.builder.provider_image.target_identifier=image_id
        self.builder.provider_image.provider_account_identifier=self.credentials_dict['username']
        self.percent_complete=100
    
    def openstack_decode_credentials(self, credentials):
        self.activity("Preparing OpenStack credentials")
        # TODO: Validate these - in particular, ensure that if some nodes are missing at least
        #       a minimal acceptable set of auth is present
        doc = libxml2.parseDoc(credentials)

        self.credentials_dict = { }
        for authprop in [ 'auth_url', 'password', 'strategy', 'tenant', 'username']:
            self.credentials_dict[authprop] = self._get_xml_node(doc, authprop)
        self.credentials_token = self._get_xml_node(doc, 'token')
        
    def _get_xml_node(self, doc, credtype):
        nodes = doc.xpathEval("//provider_credentials/openstack_credentials/%s" % (credtype))
        # OpenStack supports multiple auth schemes so not all nodes are required
        if len(nodes) < 1:
            return None

        return nodes[0].content

    def snapshot_image_on_provider(self, builder, provider, credentials, template, parameters):
        # TODO: Implement snapshot builds
        raise ImageFactoryException("Snapshot builds not currently supported on OpenStack KVM")

    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        return True

    def builder_will_create_target_image(self, builder, target, image_id, template, parameters):
        pass

    def builder_did_create_target_image(self, builder, target, image_id, template, parameters):
        pass

    def get_dynamic_provider_data(self, provider):
        try:
            xml_et = fromstring(provider)
            return xml_et.attrib
        except Exception as e:
            self.log.debug('Testing provider for XML: %s' % e)
            pass

        try:
            jload = json.loads(provider)
            return jload
        except ValueError as e:
            self.log.debug('Testing provider for JSON: %s' % e)
            pass

        return None

