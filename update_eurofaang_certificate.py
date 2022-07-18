"""
Update Eurofaang SSL certicate
using certbot renew command
on 'k8s-admin' pod
"""

from kubernetes import config
from kubernetes.client import Configuration
from kubernetes.client.api import core_v1_api
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream
import subprocess
import yaml
from schema import Schema, SchemaError, Regex


def exec_commands(api_instance):
    pod_name = 'k8s-admin'
    resp = None
    try:
        resp = api_instance.read_namespaced_pod(name=pod_name, namespace='default')
    except ApiException as e:
        if e.status != 404:
            print("Unknown error: %s" % e)
            exit(1)

    if not resp:
        print("Pod %s does not exist." % pod_name)
        exit(1)

    # Calling exec to renew certificate
    exec_command = [
        '/bin/sh',
        '-c',
        'certbot renew']
    resp = stream(api_instance.connect_get_namespaced_pod_exec,
                  pod_name,
                  'default',
                  command=exec_command,
                  stderr=True, stdin=False,
                  stdout=True, tty=False)

    if resp and 'Cert not yet due for renewal' in str(resp):
        print("EuroFAANG Certificate not yet due for renewal")
        exit(0)

    # Copying secret to eurofaang namespace
    secret_file_name = "eurofaang_tls_secret.yaml"

    # copy tls-secret from default namespace to file
    f = open(secret_file_name, "w")
    subprocess.run(["kubectl", "get", "secret", "tls-secret", "--namespace=default",
                    "-o", "yaml"], stdout=f)

    # load yaml contents in data var
    filestream = open(secret_file_name, 'r')
    data = yaml.safe_load(filestream)

    # validate schema of secret
    config_schema = Schema({
        "apiVersion": str,
        "data": {
            "tls.crt": str,
            "tls.key": str
        },
        "kind": str,
        "metadata": {
            "creationTimestamp": str,
            "name": str,
            "namespace": str,
            "resourceVersion": str,
            "selfLink": str,
            "uid": str
        },
        "type": str
    })

    try:
        config_schema.validate(data)
        print("Secret schema is valid.")

        # Update namespace of secret with dcc-eurofaang-3736-frontend
        data['metadata']['namespace'] = 'dcc-eurofaang-3736-frontend'
        with open(secret_file_name, 'w') as yaml_file:
            yaml_file.write(yaml.dump(data, default_flow_style=False))

        # delete old tls-secret in dcc-eurofaang-3736-frontend and copy the latest one
        with open(secret_file_name, "r"):
            try:
                secrets_list = api_instance.list_namespaced_secret('dcc-eurofaang-3736-frontend')
                for secret in secrets_list.items:
                    if secret.metadata.name == 'tls-secret':
                        api_instance.delete_namespaced_secret('tls-secret', 'dcc-eurofaang-3736-frontend')
                        print('Deleted old tls-secret in dcc-eurofaang-3736-frontend')
                        break

                update_secret = subprocess.run(["kubectl", "apply", "-f", "eurofaang_tls_secret.yaml"])
                if update_secret.returncode == 0:
                    print("TLS Secret copied to dcc-eurofaang-3736-frontend namespace")
                else:
                    print("ERROR copying tls-secret to dcc-eurofaang-3736-frontend namespace")

            except yaml.YAMLError as exc:
                print(exc)
    except SchemaError as se:
        raise se


def main():
    config.load_kube_config('./config')
    try:
        c = Configuration().get_default_copy()
    except AttributeError:
        c = Configuration()
        c.assert_hostname = False
    Configuration.set_default(c)
    core_v1 = core_v1_api.CoreV1Api()

    exec_commands(core_v1)


if __name__ == '__main__':
    main()
