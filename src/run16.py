#!/usr/bin/python

import sys
import re


class Memory:
    def __init__(self):
        self.context = [
            0x0000, 0x0000, 0x0000, 0x0000,  # r0 - r3
            0x0000, 0x0000, 0x0000, 0xdffe,  # r4 - r7
            0x0000, 0x0000  # pc, stack limit, carry
        ]

        self.carry = 0
        self.memory = []
        self.terminput = []
        self.cycles = 0

    def compile_assembly(self, program_list):
        if self.check(program_list):
            return '[program has errors]', '', ''
        else:
            return (*self.load(program_list), self.run())

    def reset(self):
        self.context = [
            0x0000, 0x0000, 0x0000, 0x0000,  # r0 - r3
            0x0000, 0x0000, 0x0000, 0xdffe,  # r4 - r7
            0x0000, 0x0000  # pc, stack limit, carry
        ]

        self.carry = 0
        self.memory = []
        self.terminput = []
        self.cycles = 0

    @staticmethod
    def check(program):
        for lin in program:
            flds = [l for l in re.split('[\r\t\n ]', lin) if l]
            if len(flds) != 2:
                return 1
            for f in flds:
                if f == '****':
                    return 1
        return 0

    def load(self, program):
        program_info = []
        symbols = []
        lines = 0
        codes = {
            0x0000: "and", 0x1000: "or", 0x2000: "xor", 0x3000: "slt",
            0x4000: "sltu", 0x5000: "add", 0x5001: "adc", 0x6000: "sub",
            0x6001: "sbc", 0x8000: "ldr", 0x9000: "ldc", 0xa000: "lsr",
            0xa001: "asr", 0xa002: "ror", 0x0002: "ldb", 0x1002: "stb",
            0x4002: "ldw", 0x5002: "stw", 0xc000: "bez", 0xd000: "bnz"
        }

        # load program into memory
        for lin in program:
            flds = [l for l in re.split('[\r\t\n ]', lin) if l]
            data = int(flds[1], 16)
            self.memory.append(data)
            if data & 0x0800:
                if (data & 0xf000) in codes:
                    symbols.append(
                        lin + "     %s r%d,%d" % (codes[data & 0xf000], (data & 0x0700) >> 8, (data & 0x00ff)))
                else:
                    symbols.append(lin + "     ???")
            else:
                if (data & 0xf003) in codes:
                    symbols.append(lin + "     %s r%d,r%d,r%d" % (
                        codes[data & 0xf003], (data & 0x0700) >> 8, (data & 0x00e0) >> 5, (data & 0x001c) >> 2))
                else:
                    symbols.append(lin + "     ???")
            lines += 1

        program_info.append("Program (code + data): %d bytes" % (len(self.memory) * 2))

        self.context[9] = (len(self.memory) * 2) + 2

        for i in range(lines, 28672):
            self.memory.append(0)

        self.context[7] = len(self.memory) * 2 - 2
        program_info.append("Memory size: %d" % (len(self.memory) * 2))

        return program_info, symbols

    def run(self):
        codes = {
            0x0000: "and", 0x1000: "or", 0x2000: "xor", 0x3000: "slt",
            0x4000: "sltu", 0x5000: "add", 0x5001: "adc", 0x6000: "sub",
            0x6001: "sbc", 0x8000: "ldr", 0x9000: "ldc", 0xa000: "lsr",
            0xa001: "asr", 0xa002: "ror", 0x0002: "ldb", 0x1002: "stb",
            0x4002: "ldw", 0x5002: "stw", 0xc000: "bez", 0xd000: "bnz"
        }
        cycles = 0
        args = sys.argv[1:]
        response = []

        while True:
            inst = self.memory[self.context[8] >> 1]
            last_pc = self.context[8]

            result, message = self.cycle()
            if message:
                response.append(message)
            if not result:
                break
            cycles += 1

            if self.context[7] < self.context[9]:
                response.append('stack overflow detected!')
                break

            if args:
                if inst & 0x0800:
                    response.append(
                        'pc: %04x instruction: %s r%d,%d' % (
                            last_pc, codes[inst & 0xf000], (inst & 0x0700) >> 8, (inst & 0x00ff))
                    )
                else:
                    response.append(
                        'pc: %04x instruction: %s r%d,r%d,r%d' % (
                            last_pc, codes[inst & 0xf003], (inst & 0x0700) >> 8, (inst & 0x00e0) >> 5,
                            (inst & 0x001c) >> 2)
                    )
                response.append('r0: [%04x] r1: [%04x] r2: [%04x] r3: [%04x]' % (
                    self.context[0], self.context[1], self.context[2], self.context[3]))
                response.append('r4: [%04x] r5: [%04x] r6: [%04x] r7: [%04x]\n' % (
                    self.context[4], self.context[5], self.context[6], self.context[7]))

        response.append('\n\n[ok] ')
        response.append(f'{cycles} cycles')

        return response

    def cycle(self):
        message = ''
        pc = self.context[8]

        # fetch an instruction from memory
        instruction = self.memory[pc >> 1]

        # predecode the instruction (extract opcode fields)
        opc = (instruction & 0xf000) >> 12
        imm = (instruction & 0x0800) >> 11
        rst = (instruction & 0x0700) >> 8
        rs1 = (instruction & 0x00e0) >> 5
        rs2 = (instruction & 0x001c) >> 2
        op2 = instruction & 0x0003
        immediate = instruction & 0x00ff

        # it's halt and catch fire, halt the simulator
        if instruction == 0x0003:
            return 0, message

        # decode and execute
        if imm == 0:
            if self.context[rs1] > 0x7fff:
                rs1 = self.context[rs1] - 0x10000
            else:
                rs1 = self.context[rs1]
            if self.context[rs2] > 0x7fff:
                rs2 = self.context[rs2] - 0x10000
            else:
                rs2 = self.context[rs2]
        else:
            if self.context[rst] > 0x7fff:
                rs1 = self.context[rst] - 0x10000
            else:
                rs1 = self.context[rst]
            if immediate > 0x7f:
                immediate -= 0x100
            rs2 = immediate

        if opc == 10:
            if op2 == 0:
                self.context[rst] = (rs1 & 0xffff) >> 1
            elif op2 == 1:
                self.context[rst] = rs1 >> 1
            elif op2 == 2:
                self.context[rst] = (self.carry << 15) & ((rs1 & 0xffff) >> 1)
            else:
                message += "[error (invalid shift instruction)]"
            carry = rs1 & 1
        elif (imm == 0 and (op2 == 0 or op2 == 1)) or imm == 1:
            if opc == 0:
                if imm == 1:
                    rs2 &= 0xff
                self.context[rst] = rs1 & rs2
            elif opc == 1:
                if imm == 1:
                    rs2 &= 0xff
                self.context[rst] = rs1 | rs2
            elif opc == 2:
                self.context[rst] = rs1 ^ rs2
            elif opc == 3:
                if rs1 < rs2:
                    self.context[rst] = 1
                else:
                    self.context[rst] = 0
            elif opc == 4:
                if (rs1 & 0xffff) < (rs2 & 0xffff):
                    self.context[rst] = 1
                else:
                    self.context[rst] = 0
            elif opc == 5:
                if imm == 0 and op2 == 1:
                    self.context[rst] = (rs1 & 0xffff) + (rs2 & 0xffff) + self.carry
                else:
                    self.context[rst] = (rs1 & 0xffff) + (rs2 & 0xffff)
                carry = (self.context[rst] & 0x10000) >> 16
            elif opc == 6:
                if imm == 0 and op2 == 1:
                    self.context[rst] = (rs1 & 0xffff) - (rs2 & 0xffff) - self.carry
                else:
                    self.context[rst] = (rs1 & 0xffff) - (rs2 & 0xffff)
                carry = (self.context[rst] & 0x10000) >> 16
            elif opc == 8:
                self.context[rst] = rs2
            elif opc == 9:
                self.context[rst] = (self.context[rst] << 8) | (rs2 & 0xff)
            elif opc == 12:
                if imm == 1:
                    if rs1 == 0:
                        pc = pc + rs2
                else:
                    if rs1 == 0:
                        pc = rs2 - 2
            elif opc == 13:
                if imm == 1:
                    if rs1 != 0:
                        pc = pc + rs2
                else:
                    if rs1 != 0:
                        pc = rs2 - 2
            else:
                message += "[error (invalid computation / branch instruction)]"
        elif imm == 0 and op2 == 2:
            if opc == 0:
                if rs2 & 0x1:
                    byte = self.memory[(rs2 & 0xffff) >> 1] & 0xff
                else:
                    byte = self.memory[(rs2 & 0xffff) >> 1] >> 8

                if byte > 0x7f:
                    self.context[rst] = byte - 0x100
                else:
                    self.context[rst] = byte
            elif opc == 1:
                if rs2 & 0x1:
                    self.memory[(rs2 & 0xffff) >> 1] = (self.memory[(rs2 & 0xffff) >> 1] & 0xff00) | (rs1 & 0xff)
                else:
                    self.memory[(rs2 & 0xffff) >> 1] = (self.memory[(rs2 & 0xffff) >> 1] & 0x00ff) | ((rs1 & 0xff) << 8)
            elif opc == 4:
                if (rs2 & 0xffff) == 0xf004:  # emulate an input character device (address: 61444)
                    if not self.terminput:
                        self.terminput = input() + '\0'
                    result = int(ord(self.terminput[0]))
                    self.terminput = self.terminput[1:]
                    self.context[rst] = result
                elif (rs2 & 0xffff) == 0xf006:  # emulate an input integer device (address: 61446)
                    self.context[rst] = int(input())
                else:
                    self.context[rst] = self.memory[(rs2 & 0xffff) >> 1]
            elif opc == 5:
                if (rs2 & 0xffff) == 0xf000:  # emulate an output character device (address: 61440)
                    message += chr(rs1 & 0xff)
                elif (rs2 & 0xffff) == 0xf002:  # emulate an output integer device (address: 61442)
                    message += str(rs1)
                else:
                    self.memory[(rs2 & 0xffff) >> 1] = rs1
            else:
                message += "[error (invalid load/store instruction)]"
        else:
            message += "[error (invalid instruction)]"

        # increment the program counter
        pc = pc + 2
        self.context[8] = pc

        # fix the stored word to the matching hardware size
        self.context[rst] &= 0xffff

        return 1, message

    @staticmethod
    def to_hex(n):
        return '%s' % ('0000%x' % (n & 0xffff))[-4:]


if __name__ == "__main__":
    import pathlib
    from assemble16 import Assembler

    ass = Assembler()
    aux = Memory()
    with open(str((pathlib.Path(__file__).parent.parent / 'examples' / 'ninetoone.asm').absolute())) as f:
        out = ass.generate_assembly(f.read().split('\n'))
        print(''.join(map(str, aux.compile_assembly(out))))
