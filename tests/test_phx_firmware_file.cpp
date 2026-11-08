#include "../tools/phxctl/fw_file.h"
#include <cassert>
#include <cstdio>
int main() {
    uint32_t value;
    assert(phxParseUint32("0x100", &value) && value == 256);
    assert(!phxParseUint32("4294967296", &value));
    assert(!phxParseUint32("-1", &value));
    assert(!phxParseUint32("32tail", &value));
    assert(!phxParseUint32("", &value));
    FILE *f = tmpfile(); assert(f);
    unsigned char bytes[32] = {}; assert(fwrite(bytes,1,sizeof bytes,f)==sizeof bytes);
    assert(phxFirmwareRange(f,0,32)); assert(ftello(f)==0);
    assert(phxFirmwareRange(f,16,16)); assert(ftello(f)==16);
    assert(!phxFirmwareRange(f,16,17));
    assert(!phxFirmwareRange(f,0,0));
    assert(!phxFirmwareRange(f,0xffffffffu,32));
    assert(!phxFirmwareRange(f,32,1));
    assert(!phxFirmwareRange(nullptr,0,1));
    fclose(f);
    puts("[PASS] full firmware file range verified before staging; EOF/overflow/empty ranges refused");
}
