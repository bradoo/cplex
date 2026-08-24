dvar float+ xA;
dvar float+ xB;
dvar float+ xC;

maximize
    40*xA + 30*xB + 50*xC;

subject to {
    material:
        3*xA + 2*xB + 4*xC <= 120;
    labor:
        2*xA + 1*xB + 3*xC <= 100;
}
