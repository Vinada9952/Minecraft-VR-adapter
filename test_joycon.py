from pyjoycon import get_L_ids, get_R_ids

print("Recherche des Joy-Con...")

print("\nJoy-Con gauche :")
left = get_L_ids()
print(left)

print("\nJoy-Con droit :")
right = get_R_ids()
print(right)