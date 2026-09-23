// MongoDB init script — runs once when the container is first created
// Sets up the cabProcess perimeter so Railway notification cards work

db = db.getSiblingDB('operator-fabric');

db.perimeter.updateOne(
  { _id: 'cabProcess' },
  { $set: {
      process: 'cabProcess',
      stateRights: [{ state: 'messageState', right: 'ReceiveAndWrite' }]
  }},
  { upsert: true }
);

db.group.updateOne(
  { _id: 'Planner' },
  { $addToSet: { perimeters: 'cabProcess' } }
);

db.group.updateOne(
  { _id: 'Dispatcher' },
  { $addToSet: { perimeters: 'cabProcess' } }
);

db.group.updateOne(
  { _id: 'ReadOnly' },
  { $addToSet: { perimeters: 'cabProcess' } }
);

print('cabProcess perimeter initialized');
