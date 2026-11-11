// One colour per train, by its place in the context's `trains`, the same in every Railway view.
const TRAIN_COLORS = ['#0084d4', '#00b388', '#7b5cd6', '#daaa00', '#e0607e', '#4a4a4a']

export const trainColor = (index: number) => TRAIN_COLORS[index % TRAIN_COLORS.length]
