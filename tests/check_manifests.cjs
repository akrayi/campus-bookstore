// Offline structural checks; no Kubernetes cluster is changed.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const YAML = require('yaml');
const root = path.resolve(__dirname, '..');
const documents = [];
for (const folder of ['k8s', 'monitoring', 'infra']) {
  for (const name of fs.readdirSync(path.join(root, folder)).filter((name) => name.endsWith('.yaml'))) {
    for (const document of YAML.parseAllDocuments(fs.readFileSync(path.join(root, folder, name), 'utf8'))) {
      assert.deepEqual(document.errors, [], `Valid YAML: ${folder}/${name}`);
      const value = document.toJSON();
      if (value?.apiVersion) documents.push(value);
    }
  }
}
const resource = (kind, name, namespace) => documents.find((d) => d.kind === kind && d.metadata.name === name && d.metadata.namespace === namespace);
for (const deployment of documents.filter((d) => d.kind === 'Deployment')) {
  const namespace = deployment.metadata.namespace;
  assert.ok(documents.some((d) => d.kind === 'Namespace' && d.metadata.name === namespace) || namespace === 'monitoring');
  const pod = deployment.spec.template;
  for (const [key, value] of Object.entries(deployment.spec.selector.matchLabels)) assert.equal(pod.metadata.labels[key], value);
  for (const volume of pod.spec.volumes || []) {
    if (volume.configMap) assert.ok(resource('ConfigMap', volume.configMap.name, namespace), `Missing ConfigMap ${volume.configMap.name}`);
    if (volume.persistentVolumeClaim) assert.ok(resource('PersistentVolumeClaim', volume.persistentVolumeClaim.claimName, namespace));
  }
  for (const container of pod.spec.containers) {
    for (const source of container.envFrom || []) if (source.configMapRef) assert.ok(resource('ConfigMap', source.configMapRef.name, namespace));
  }
}
const schema = resource('ConfigMap', 'orders-db-schema', 'campus-bookstore').data['schema.sql'];
assert.equal(schema.trim(), fs.readFileSync(path.join(root, 'order-service/schema.sql'), 'utf8').replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').trim(), 'Kubernetes and Compose order schemas match');
for (const binding of documents.filter((d) => d.kind === 'RoleBinding')) {
  assert.ok(resource(binding.roleRef.kind, binding.roleRef.name, binding.metadata.namespace));
  for (const subject of binding.subjects) if (subject.kind === 'ServiceAccount') assert.ok(resource(subject.kind, subject.name, subject.namespace));
}
for (const service of documents.filter((d) => d.kind === 'Service' && d.metadata.namespace === 'campus-bookstore')) {
  const deployment = documents.find((d) => d.kind === 'Deployment' && d.metadata.namespace === service.metadata.namespace && Object.entries(service.spec.selector).every(([key, value]) => d.spec.template.metadata.labels[key] === value));
  assert.ok(deployment, `Service ${service.metadata.name} must select a Deployment`);
  const ports = deployment.spec.template.spec.containers.flatMap((c) => c.ports || []);
  for (const port of service.spec.ports) assert.ok(ports.some((p) => typeof port.targetPort === 'number' ? p.containerPort === port.targetPort : p.name === port.targetPort), `Service ${service.metadata.name}: missing target port`);
}
const monitored = documents.find((d) => d.kind === 'ServiceMonitor' && d.metadata.name === 'bookstore-apis');
assert.ok(monitored);
for (const name of ['order-service', 'product-service']) assert.equal(resource('Service', name, 'campus-bookstore').metadata.labels['bookstore-metrics'], 'enabled');
console.log(`Validated ${documents.length} Kubernetes resources, YAML syntax, schemas, Service ports, metrics discovery, and local references. The database Secret is created by scripts/deploy.py.`);
