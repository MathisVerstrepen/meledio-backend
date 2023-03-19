import numpy as np
from scipy.io import wavfile
import matplotlib.pyplot as plt
import os

chapter = [
		{
			"title": "Legend of the Eagle Bearer (Main Theme",
			"timestamp": 0.0
		},
		{
			"title": "The 300",
			"timestamp": 234.0
		},
		{
			"title": "Enter the Animus",
			"timestamp": 497.0
		},
		{
			"title": "Odyssey (Greek version",
			"timestamp": 610.0
		},
		{
			"title": "Phoibe the Orphan",
			"timestamp": 800.0
		},
		{
			"title": "Kephallonia Island",
			"timestamp": 870.0
		},
		{
			"title": "Markos",
			"timestamp": 998.0
		},
		{
			"title": "Revenge of the Wolves",
			"timestamp": 1051.0
		},
		{
			"title": "Barnabas",
			"timestamp": 1184.0
		},
		{
			"title": "Pirates, Thugs, and Bandits",
			"timestamp": 1262.0
		},
		{
			"title": "Assassin's Creed",
			"timestamp": 1537.0
		},
		{
			"title": "Conflict on the Seas",
			"timestamp": 1713.0
		},
		{
			"title": "The Shores of Megaris",
			"timestamp": 1898.0
		},
		{
			"title": "Athenian Fighters",
			"timestamp": 1997.0
		},
		{
			"title": "Korinth",
			"timestamp": 2237.0
		},
		{
			"title": "On the Battlefield",
			"timestamp": 2297.0
		},
		{
			"title": "Things Fall Apart",
			"timestamp": 2595.0
		},
		{
			"title": "Nikolaos’s Fate",
			"timestamp": 2774.0
		},
		{
			"title": "The Secret Land of Apollo",
			"timestamp": 2881.0
		},
		{
			"title": "Conversations",
			"timestamp": 2991.0
		},
		{
			"title": "Guards of the Cult",
			"timestamp": 3095.0
		},
		{
			"title": "Delphi",
			"timestamp": 3304.0
		},
		{
			"title": "The Cult of Kosmos",
			"timestamp": 3371.0
		},
		{
			"title": "Leonidas Fallen",
			"timestamp": 3628.0
		},
		{
			"title": "Legendary Heirloom",
			"timestamp": 3769.0
		},
		{
			"title": "The Hills of Attika",
			"timestamp": 3898.0
		},
		{
			"title": "Sokrates",
			"timestamp": 4055.0
		},
		{
			"title": "Naxos Island",
			"timestamp": 4132.0
		},
		{
			"title": "Reunited",
			"timestamp": 4223.0
		},
		{
			"title": "Myrrine",
			"timestamp": 4356.0
		},
		{
			"title": "Ariadnes's Fate",
			"timestamp": 4508.0
		},
		{
			"title": "Forgotten Isle",
			"timestamp": 4567.0
		},
		{
			"title": "One-Eyed Monster",
			"timestamp": 4686.0
		},
		{
			"title": "The Messara Plain",
			"timestamp": 4917.0
		},
		{
			"title": "Kydonia",
			"timestamp": 5029.0
		},
		{
			"title": "Atlantis",
			"timestamp": 5090.0
		},
		{
			"title": "The Sacred Land of Artemis",
			"timestamp": 5192.0
		},
		{
			"title": "Sparta",
			"timestamp": 5284.0
		},
		{
			"title": "A Spartan Fight",
			"timestamp": 5349.0
		},
		{
			"title": "Brasidas",
			"timestamp": 5585.0
		},
		{
			"title": "Valley of the Two Kings",
			"timestamp": 5661.0
		},
		{
			"title": "Legendary Animals",
			"timestamp": 5757.0
		},
		{
			"title": "Ash Hills",
			"timestamp": 5922.0
		},
		{
			"title": "Labyrinth of Lost Souls",
			"timestamp": 6022.0
		},
		{
			"title": "The Minotaur",
			"timestamp": 6124.0
		},
		{
			"title": "Gortyn",
			"timestamp": 6331.0
		},
		{
			"title": "Athens, Birthplace of Democracy",
			"timestamp": 6392.0
		},
		{
			"title": "Phoibe’s Fate",
			"timestamp": 6457.0
		},
		{
			"title": "Pandora’s Cove",
			"timestamp": 6531.0
		},
		{
			"title": "Petrified Temple",
			"timestamp": 6647.0
		},
		{
			"title": "Medusa",
			"timestamp": 6761.0
		},
		{
			"title": "Mytilene",
			"timestamp": 6962.0
		},
		{
			"title": "Sanctuary of Apollo",
			"timestamp": 7034.0
		},
		{
			"title": "A Happy Family",
			"timestamp": 7095.0
		},
		{
			"title": "Passing the Torch",
			"timestamp": 7375.0
		},
		{
			"title": "Odyssey (Modern Version",
			"timestamp": 7480.0
		}
	]
# os.remove('temp.png')
AudioName = "../../../bacchus/audio/103054/temp.wav.wav" # Audio File

# read WAV file using scipy.io.wavfile
fs_wav, data_wav = wavfile.read(AudioName)

print('Sampling Frequency = {} Hz'.format(fs_wav))
print('Signal Duration = {} seconds'.format(data_wav.shape[0] / fs_wav))


time_wav = np.arange(0, len(data_wav)) / fs_wav

# plt.plot(time_wav, data_wav[:, 0], label='left channel')
# # plt.plot(time_wav, data_wav[:, 1], label='right channel')
# plt.savefig('temp.png')

def index_moyenne_proche_de_zero(arr):
    abs_arr = np.abs(arr)
    moyennes = []
    for i in range(0, len(arr), 100):
        debut = max(0, i-100)
        fin = min(len(arr), i+100)
        moyenne = np.mean(abs_arr[debut:fin])
        moyennes.append(moyenne)
    moyennes = np.array(moyennes)
    return np.argmin(moyennes)*100

for ch in chapter[1:]:
    print(ch['title'])
    ch_wav = data_wav[int((ch['timestamp'] - 20) * fs_wav):int((ch['timestamp'] + 20) * fs_wav), 0]
    
    # abs_mean = np.mean(np.abs(ch_wav))

    # Calcul de l'indice de la zone où la moyenne des valeurs est la plus proche de zéro
    closest_index = index_moyenne_proche_de_zero(ch_wav)

    print("L'indice de la zone où les valeurs sont en moyenne les plus proches de zéro est :", closest_index)
    ch['corrected_timestamp'] = ch['timestamp'] - 20 + closest_index / fs_wav
    
    plt.figure()
    plt.plot(time_wav[int((ch['timestamp'] - 20) * fs_wav):int((ch['timestamp'] + 20) * fs_wav)], ch_wav, label=ch['title'])
    plt.vlines(ch['corrected_timestamp'], -10000, 10000, color='green')
    plt.vlines(ch['timestamp'], -10000, 10000, color='red')
    plt.savefig(f'spectrum/{ch["title"]}.png')
    
    # extract quiet part of the signal
    
    
for ch in chapter[1:]:
    print(ch['title'], ch["timestamp"], ch['corrected_timestamp'])