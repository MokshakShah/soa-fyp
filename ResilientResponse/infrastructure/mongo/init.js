// MongoDB initialization script for ResilientResponse
db = db.getSiblingDB('resilientresponse');

// Core collections
db.createCollection('admins');
db.createCollection('alerts');
db.createCollection('incidents');
db.createCollection('hospitals');
db.createCollection('police_stations');
db.createCollection('resources');
db.createCollection('workflows');
db.createCollection('workflow_events');
db.createCollection('notifications');
db.createCollection('service_registry');
db.createCollection('service_health');

// Indexes for performance
db.admins.createIndex({ email: 1 }, { unique: true });
db.hospitals.createIndex({ city: 1 });
db.hospitals.createIndex({ status: 1 });
db.police_stations.createIndex({ city: 1 });
db.police_stations.createIndex({ status: 1 });
db.resources.createIndex({ type: 1 });
db.resources.createIndex({ status: 1 });
db.alerts.createIndex({ status: 1 });
db.alerts.createIndex({ created_at: -1 });
db.incidents.createIndex({ status: 1 });
db.incidents.createIndex({ created_at: -1 });
db.workflows.createIndex({ incident_id: 1 });
db.workflows.createIndex({ status: 1 });
db.notifications.createIndex({ incident_id: 1 });
db.notifications.createIndex({ created_at: -1 });

print('ResilientResponse Phase 2 database initialized.');
