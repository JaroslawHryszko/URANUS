from uranus import Uranus
u = Uranus(['impact', 'probability'], ['0', '1', '2', '3', '4'])

a, b, c = u.next_to_process()

while True:
    u.show_status()
    while True:
        if not(a is None) and not(b is None) and not(c is None):
            print(f"1 if {u.p_names[c]} of risk {a} {u.e_names[a]} is LOWER than of risk {b} {u.e_names[b]}")
            print(f"2 if {u.p_names[c]} of risk {a} {u.e_names[a]} is GREATER than of risk {b} {u.e_names[b]}")
        print(f"3 remove element   4 add element   5 remove parameter    6 add parameter   7 swap parameters   8 prioritize   9 exit")

        inp = input()
        if inp in ['1','2','3','4','5','6','7','8','9']:
            break
    if inp == '1':
        u.set_priority(0)
    elif inp == '2':
        u.set_priority(1)
    elif inp == '3':
        idx = input("Podaj ID elementu")
        status = u.remove_element(int(idx))
        print(f"Status: {status}")
    elif inp == '4':
        newname = input("Podaj nazwe elementu ")
        status = u.add_element(newname)
        print(f"Status: {status}")
    elif inp == '5':
        idx = input("Podaj ID parametru")
        status = u.remove_parameter(int(idx))
        print(f"Status: {status}")
    elif inp == '6':
        newname = input("Podaj nazwe parametru ")
        status = u.add_parameter(newname)
        print(f"Status: {status}")
    elif inp == '7':
        p1 = input("Podaj ID parametru 1")
        p2 = input("Podaj ID parametru 2")
        status = u.swap_parameter_priorities(int(p1), int(p2))
        print(f"Status: {status}")
    elif inp == '8':
        pl = u.prioritized_list()
        print(f"Prioritized list: {pl}")
    elif inp == '9':
        break
    a, b, c = u.next_to_process()
print("This is all")

print(u.prioritized_list())
u.show_status()
