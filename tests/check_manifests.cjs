// Offline structural checks; no Kubernetes cluster is changed.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const YAML = require('yaml');
const root = path.resolve(__dirname, '..');
const documents = [];
for (const folder of ['k8s', 'monitoring']) {
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
console.log(`Validated ${documents.length} Kubernetes resources, YAML syntax, schema consistency, and local resource references. Secrets and the monitoring namespace are external prerequisites.`);
