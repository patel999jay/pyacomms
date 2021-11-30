#__author__ = 'Eric'

from bitstring import BitStream, BitArray
from datetime import datetime
from .messageparams import data_from_hexstring

mission_modes = {0: "Mission completed",
                 1: "Manual",
                 2: "Test",
                 3: "Fault",
                 5: "Redirected",
                 6: "Normal", }

ranger_mission_modes = {1: "Pre-mission",
                        2: "Run",
                        5: "Completed"}

command_codes = {1: "Abort to end",
                 2: "Abort immediately",
                 3: "Start mission",
                 7: "Enable ranger ping",
                 8: "Disable ranger ping",
                 15: "Dump redirect commands",
                 17: "Abort to start",
                 18: "Abort to destination",
                 19: "Dump redirect except current"}


def LatLon(object):
    def __init__(self, lat_degrees=None, lon_degrees=None, lat_minutes=0, lon_minutes=None, lat_seconds=0, lon_seconds=None):
        if lat_degrees is not None:
            self._lat_degrees = float(lat_degrees)
            self._lat_degrees += lat_minutes/60
            self._lat_degrees += lat_seconds/(60*60)

        if lon_degrees is not None:
            self._lon_degrees = float(lon_degrees)
            self._lon_degrees += lon_minutes/60
            self._lon_degrees += lon_seconds/(60*60)



def decode_latlon(bit_array):
    if bit_array is None:
        raise ValueError

    # switch to big endian
    bit_array.byteswap()

    # sign extend
    if bit_array[0] == 1:
        bit_array.prepend('0xFF')
    else:
        bit_array.prepend('0x00')

    # Do conversion and return
    return bit_array.intbe * (180.0 / (2**23 - 1))


def decode_time_date(databits, year=None):
    databits.byteswap()

    month = databits.read('uint:4')
    day = databits.read('uint:5')
    hour = databits.read('uint:5')
    minute = databits.read('uint:6')
    second = databits.read('uint:4') * 4

    if year == None:
        year = datetime.utcnow().year

    return datetime(year, month, day, hour, minute, second)


def decode_depth(encoded_depth):
    if encoded_depth <= 1000:
        return encoded_depth * 0.1
    elif encoded_depth <= 1500:
        return 100 + (encoded_depth - 1000) * 0.2
    elif encoded_depth <= 3100:
        return 200 + (encoded_depth - 1500) * 0.5
    elif encoded_depth <= 8100:
        return 1000 + (encoded_depth - 3100)
    else:
        return 6000


def decode_mission_mode_and_depth(encoded_bits):
    encoded_bits.byteswap()

    mission_mode_code = encoded_bits[0:3].uint
    depth = decode_depth(encoded_bits[3:].uint)

    mission_mode = mission_modes[mission_mode_code]

    return (mission_mode, depth)


class CclDecoder(object):
    ''' This attaches to the incoming dataframe queue and raises events when recognized messages are received
    '''

    @staticmethod
    def decode_dataframe(dataframe):
        msg_class = CclTypes[dataframe.data[0]]
        ccl_message = msg_class.from_data(dataframe.data)
        ccl_message['src'] = dataframe.src
        ccl_message['dest'] = dataframe.dest

        return ccl_message

    @staticmethod
    def decode_data(data):
        msg_class = CclTypes[data[0]]
        ccl_message = msg_class.from_data(data)

        return ccl_message

    @staticmethod
    def decode_hex_string(hex_data):
        data = data_from_hexstring(hex_data)
        msg_class = CclTypes[data[0]]
        ccl_message = msg_class.from_data(data)

        return ccl_message

    def __init__(self, modem):
        modem.rxframe_listeners.append(self.on_modem_rxframe)
        self.modem = modem
        self.ccl_listeners = []

    def on_modem_rxframe(self, dataframe):
        # Check for all the CCL types
        # try:
        ccl_message = self.decode_dataframe(dataframe)
        self.on_ccl_received(ccl_message)


        #except:
        #    pass

    def on_ccl_received(self, ccl_message):
        for listener in self.ccl_listeners:
            listener(ccl_message)


class MdatCommandMessage(dict):
    fields = ('mode', 'command', 'command_code' 'parameter')

    def __init__(self, command_code=None, command=None):
        self['mode'] = 'MDAT_COMMAND'
        self['command_code'] = command_code
        self['command'] = command_codes[command_code]
        self['parameter'] = bytearray(28)

    @property
    def as_data(self):
        databytes = bytearray([11, 0, 0])
        databytes.append(self['command_code'])
        databytes.append(self['parameter'])
        return databytes

    @classmethod
    def from_data(cls, databytes):
        values = dict.fromkeys(MdatCommandMessage.fields)

        # accept either the full frame payload or just the data after the CCL type identifier
        if (len(databytes) > 31):
            databytes = databytes[1:-1]

        values['mode'] = 'MDAT_COMMAND'

        values['command_code'] = databytes[2]
        values['command'] = command_codes[databytes[2]]
        values['parameter'] = databytes[3:-1]

        # Make a message
        mdat_command = cls(values)

        return mdat_command


class MdatRangerMessage(dict):
    fields = ('mode', 'latitude', 'longitude',
              'fix_age', 'heading', 'mission_mode',
              'depth', 'major_fault', 'mission_leg', 'num_legs', 'speed_kt',
              'battery_percent')

    @classmethod
    def from_data(cls, databytes):
        values = dict.fromkeys(MdatRangerMessage.fields)

        # accept either the full frame payload or just the data after the CCL type identifier
        if (len(databytes) > 31):
            databytes = databytes[1:-1]

        values['mode'] = 'MDAT_RANGER'

        hex_string = ''.join('{:02x}'.format(x) for x in databytes)
        # Now, hex_string is a 62-character string

        # Latitude
        lat_deg = int(hex_string[1:3])
        lat_dir = 'N' if hex_string[3] == 'a' else 'S'
        lat_min = float(hex_string[4:10]) / 10000.
        values['latitude'] = "{}{}{}".format(lat_deg, lat_dir, lat_min)

        values['lat_deg'] = lat_deg
        values['lat_decmin'] = lat_min
        values['lat_dir'] = lat_dir


        # Longitude
        lon_deg = int(hex_string[10:13])
        lon_dir = 'E' if hex_string[13] == 'b' else 'W'
        lon_min = float(hex_string[14:20]) / 10000.

        values['longitude'] = "{}{}{}".format(lon_deg, lon_dir, lon_min)

        values['lon_deg'] = lon_deg
        values['lon_decmin'] = lon_min
        values['lon_dir'] = lon_dir



        values['mission_leg'] = int(hex_string[20:24])
        values['num_legs'] = int(hex_string[24:28])

        values['time_remaining'] = "{}:{}".format(hex_string[28:30], hex_string[30:32])

        values['battery_percent'] = int(hex_string[32:34])
        values['speed_kt'] = "{}.{}".format(hex_string[34], hex_string[35])

        values['heading'] = int(hex_string[36:39])

        values['fix_age'] = "{}:{}".format(hex_string[40:42], hex_string[42:44])

        values['depth'] = int(hex_string[44:46])

        values['mission_mode'] = ranger_mission_modes.get(int(hex_string[46:48]),
                                                          "Unknown mode ({})".format(hex_string[46:48]))

        values['major_fault'] = True if (hex_string[48] == '8') else False


        # Make a message
        mdat_ranger = cls(values)

        return mdat_ranger


class MdatStateMessage(dict):
    '''
    A single MDAT_STATE message
    '''

    # Note that we don't override the dict initalizer.

    fields = ('mode', 'latitude', 'longitude',
              'fix_age', 'time_date', 'heading', 'mission_mode',
              'depth', 'faults_bits', 'mission_leg', 'estimated_velocity', 'objective_index',
              'power_watts', 'goal_latitude', 'goal_longitude', 'battery_percent', 'gfi_percent',
              'pitch', 'oil')

    # This automagically retrieves values from the dictionary when they are referenced as properties.
    # Whether this is awesome or sucks is open to debate.
    def __getattr__(self, item):
        """Maps values to attributes.
        Only called if there *isn't* an attribute with this name
        """
        try:
            return self.__getitem__(item)
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, item, value):
        """Maps attributes to values.
        Only if we are initialised
        """
        if '_MdatStateMessage__initialized' not in self.__dict__:  # this test allows attributes to be set in the __init__ method
            return dict.__setattr__(self, item, value)
        elif item in self.__dict__:  # any normal attributes are handled normally
            dict.__setattr__(self, item, value)
        else:
            self.__setitem__(item, value)

    def __str__(self):
        ''' Default human-readable version
        Doesn't show all parameters, just the most common ones.'''
        hrstr = "State Message:\t{ts}\t{lat}\t{lon}".format(
            ts=self['time_date'], lat=self['latitude'], lon=self['longitude'])

        return hrstr


    @classmethod
    def from_data(cls, databytes):

        values = dict.fromkeys(MdatStateMessage.fields)

        # accept either the full frame payload or just the data after the CCL type identifier
        if (len(databytes) > 31):
            databytes = databytes[1:]

        d = BitStream(bytes=databytes)

        values['mode'] = 'MDAT_STATE'

        lat_bits = BitArray(d.read('bits:24'))
        values['latitude'] = decode_latlon(lat_bits)

        lon_bits = BitArray(d.read('bits:24'))
        values['longitude'] = decode_latlon(lon_bits)

        values['fix_age'] = d.read('uint:8') * 4
        values['time_date'] = decode_time_date(d.read('bits:24'))
        values['heading'] = d.read('uint:8') * (360.0 / 255.0)

        mission_mode_depth_bits = d.read('bits:16')
        (values['mission_mode'], values['depth']) = decode_mission_mode_and_depth(mission_mode_depth_bits)
        values['faults_bits'] = d.read('bits:40')
        values['mission_leg'] = d.read('uint:8')
        values['estimated_velocity'] = d.read('uint:8') / 25.0
        values['objective_index'] = d.read('uint:8')
        values['power_watts'] = d.read('uint:8') * 4.0

        goal_lat_bits = BitArray(d.read('bits:24'))
        values['goal_latitude'] = decode_latlon(goal_lat_bits)
        goal_lon_bits = BitArray(d.read('bits:24'))
        values['goal_longitude'] = decode_latlon(goal_lon_bits)

        values['battery_percent'] = d.read('uint:8')

        gfi_pitch_oil_encoded = BitArray(d.read('bits:16'))
        gfi_pitch_oil_encoded.byteswap()
        values['gfi_percent'] = gfi_pitch_oil_encoded[11:].uint * 100.0 / 31.0
        values['oil'] = gfi_pitch_oil_encoded[6:11].uint * 100.0 / 31.0
        values['pitch'] = gfi_pitch_oil_encoded[0:6].int * 180.0 / 63.0

        # Make a message
        mdat_state = cls(values)

        return mdat_state


CclTypes = {11: MdatCommandMessage,
            14: MdatStateMessage,
            0x10: MdatRangerMessage}
