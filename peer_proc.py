import threading
import time
import shutil
import json
from file_splitter import *
# from file_splitter import *
from TCP_sender import *
from TCP_receiver import *
# from peer_test_define import *
import socket
import bencodepy
import queue
import hashlib

class Peer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.seeder_host = host
        self.seeder_port = None
        self.seeder_socket = None
        self.peer_id = 0
        self.completed_list = []
        self.uncompleted_list = []
        self.security_code = 0
        self.client_socket = None
        self.tracker_address = ()
        self.tracker_response_queue = queue.Queue()
        self.tracker_request_lock = 0       # Lock sending message to tracker (1-lock & 0-unlock)
        self.user_command_queue = queue.Queue()

    ########################## Misc method (start) ##########################################
    def load_param(self, json_path):
        with open(json_path, "r") as file:
            torrent_list = json.load(file)
        self.security_code = torrent_list["security_code"]
        self.tracker_address = (torrent_list["tracker_ip"], torrent_list["tracker_port"])
        self.completed_list = torrent_list["completed"]
        self.uncompleted_list = torrent_list["uncompleted"]

    def user_login(self):
        # User login
        peer_username = input("Username: ")
        peer_password = input("Password: ")
        # Hash login information
        security_code = peer_username + peer_password
        # Username: admin
        # Password: 1
        while security_code != self.security_code:
            print("Error: Wrong username or password. Please try again")
            # User login
            peer_username = input("Username: ")
            peer_password = input("Password: ")
            # Hash login information
            security_code = peer_username + peer_password

    def hash_file_name(self, file_name):
        file_name_bytes = file_name.encode('utf-8')
        hashed_bytes = hashlib.sha256(file_name_bytes)
        hashed_string = hashed_bytes.hexdigest()
        return hashed_string

    def get_metainfo(self, torrent_path):
        if os.path.exists(torrent_path):
            # Read the JSON file
            with open(torrent_path, 'r') as file:
                metainfo_dict = json.load(file)
        else:
            print("Error: The path of torrent file is not exist")
            return {}
        return metainfo_dict

    def metainfo_verification(self, metainfo_dict):
        info_hash_key = 'info_hash'
        pieces_num_key = 'pieces'
        pieces_path_key = 'pieces_path'
        if not isinstance(metainfo_dict, dict):
            print(f"Error: The torrent file is invalid.")
            return False
        if info_hash_key not in metainfo_dict:
            print(f"Error: The torrent file is invalid.")
            return False
        if pieces_num_key not in metainfo_dict:
            print(f"Error: The torrent file is invalid.")
            return False
        if pieces_path_key not in metainfo_dict:
            print(f"Error: The torrent file is invalid.")
            return False

    def get_peers_list_msg(self, message):
        # Get 'peers' key
        peer_dict = message['BODY']['peers']
        # List of pairs (ip, port)
        peers_list = []
        for peer_info in peer_dict:
            # Lấy giá trị ip và port từ mỗi phần tử
            ip = peer_info['ip']
            port = peer_info['port']
            # Thêm cặp giá trị (ip, port) vào mảng mới
            peers_list.append((ip, port))
        return peers_list

    def pre_encode_convert(self, in_dict):
        if isinstance(in_dict, str):
            return in_dict.encode()
        elif isinstance(in_dict, dict):
            return {self.pre_encode_convert(key): self.pre_encode_convert(value) for key, value in in_dict.items()}
        elif isinstance(in_dict, list):
            return [self.pre_encode_convert(item) for item in in_dict]
        else:
            return in_dict

    def post_decode_convert(self, in_dict):
        if isinstance(in_dict, bytes):
            return in_dict.decode()
        elif isinstance(in_dict, dict):
            return {self.post_decode_convert(key): self.post_decode_convert(value) for key, value in in_dict.items()}
        elif isinstance(in_dict, list):
            return [self.post_decode_convert(item) for item in in_dict]
        else:
            return in_dict

    def find_unused_port(self, start_port=5001, end_port=65535):
        for port in range(start_port, end_port + 1):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('localhost', port))
                except OSError:
                    # Port is already in use
                    continue
                return port
        raise Exception("Error: No unused port found in the specified range (You are using too many resources)")

    def handle_leecher_connection(self, receiver_socket, listen_port):

        listen_socket = socket.socket()
        listen_socket.bind(('localhost', listen_port))
        listen_socket.listen(5)
        while True:
            # to do
            break

    # Searching folder function
    def search_completed_list(self, info_hash):
        for item in self.completed_list:
            if item['info_hash'] == info_hash:
                return item['pieces_path']
        return False

    # Searching id function
    def search_chunk_file(self, folder_path, id):

        files = os.listdir(folder_path)  # Get a list of all files in the folder

        filename_to_search = f"abc_pdf_{id}.bin"  # Construct the filename to search for

        if filename_to_search in files:  # Check if the file exists in the folder
            return os.path.join(folder_path, filename_to_search)

        return False

    def message_seeder_checking(self, response_seeder, key, key_of_key):
        if key not in response_seeder:
            print("Error: The message of seeder is invalid")
            return 0
        if key_of_key not in response_seeder["HEADER"]:
            print("Error: The message of seeder is invalid")
            return 0
        return 1
    ########################## Misc method (end) ##########################################

    ########################## Handling method (start) ##########################################

    def upload_handle(self, file_path):
        # Description: Hàm sẽ xử lý việc tách file thành các pieces và lưu vào folder tương ứng, sau đó cập nhật file vào completed_list
        # Param: file_path: đường dẫn tới file cần upload
        # DuongDo:  -> Copy file trên vào folder pieces_folder
        #           -> Tạo 1 folder có định dạng tên là <file_name>_<file_exten> (vd: adc.pdf -> folder tên là 'abc_pdf')
        #           -> Tách file đó vào bên trong folder trên
        #           -> Tạo ra 1 mã info_hash từ tên file (info_hash = self.hash_file_name(<file_name>))
        #           -> Tạo 1 metainfo_dictionary gồm thông tin (info_hash, pieces_path và pieces) và thêm vào self.completed_list (Nhìn định daạng trong file TorrentList.json để hiểu rõ thêm)
        #           metainfo_dictionary = {
        #               "info_hash": "ase231r3r13",
        #               "pieces_path": "pieces_folder/abc_pdf",
        #               "pieces": 36
        #           }
        #           -> Tạo mới 1 file `.json` có tên là `<file_name>_metainfo.json` vào trong folder metainfo_folder
        #           -> Lưu dictionary của bước trên vào file '.json' đó (có thể hiểu đây là file .torrent của nhóm mình)
        # Ví dụ về các tham số
        #                   self.upload_handle('\\hehe_folder\\myCV.pdf')
        #
        # Ví dụ về định dạng tách:
        #       -> Tách nó ra 1 folder gồm các piece (giả sử dc 100 mảnh)
        #           folder name:    myCV_pdf            -> Định dạng: <file_name>_<type>
        #           folder_path     /pieces_folder/     -> Nằm trong folder pieces_folder
        #           piece name:     myCV_pdf_0.bin      -> Định dạng: <folder_name>_<piece_num>.bin
        #                           myCV_pdf_1.bin
        #                           myCV_pdf_2.bin
        #                           .............
        #                           myCV_pdf_99.bin

        # Make 'pieces folder'
        pieces_folder = 'pieces_folder' # Save to working directory

        # Check if exist or not
        if not os.path.exists(pieces_folder):
            os.makedirs(pieces_folder)

        # Destination path =))
        dest_path = os.path.join(pieces_folder, os.path.basename(file_path))

        # Copy the file to pieces_folder
        shutil.copyfile(file_path, dest_path)

        # Get the name & exten from the path
        base_name = os.path.basename(file_path)
        file_name, file_exten = os.path.splitext(base_name)

        # Create a new folder
        new_folder_name = f"{file_name}_{file_exten.lstrip('.')}"
        new_folder_path = os.path.join(pieces_folder, new_folder_name)

        # Check existing
        if not os.path.exists(new_folder_path):
            os.makedirs(new_folder_path)

        # Split file into chunks
        chunk_size = 50 * 1024 # Just for example
        num_chunks = file_split(dest_path, chunk_size)

        # Move to THE folder
        for i in range(num_chunks):
            chunk_file = f"{file_name}_{file_exten}_{i}.bin"
            shutil.move(chunk_file,new_folder_path)

        # Create info_hash
        info_hash = self.hash_file_name(file_name)

        # Add new item into completed list
        def add_to_completed(info_hash, pieces_path, pieces):
            with open('TorrentList.json', 'r') as f:
                data = json.load(f)

            # Create the new item
            new_item = {
                "info_hash": info_hash,
                "pieces_path": pieces_path,
                "pieces": pieces
            }

            # Add the new item to the 'self.completed_list' list
            self.completed_list.append(new_item)

            # Write the data back to the file
            with open('TorrentList.json', 'w') as f:
                json.dump(data, f, indent=4)

        ##
        def add_to_metainfo_file(file_name, info_hash, pieces_path, pieces):
            # Create the new item
            new_item = {
                "info_hash": info_hash,
                "pieces_path": pieces_path,
                "pieces": pieces
            }

            # Create the 'metainfo_folder' if it doesn't exist
            if not os.path.exists('metainfo_folder'):
                os.makedirs('metainfo_folder')

            # Create the new JSON file and add the new item to it
            with open(f'metainfo_folder/{file_name}_metainfo.json', 'w') as f:
                json.dump(new_item, f, indent=4)

        add_to_completed(info_hash, new_folder_path, num_chunks)
        add_to_metainfo_file(file_name, info_hash, new_folder_path, num_chunks)

        return

    def download_handle(self, torrent_path):
        # Description:  Người dùng cung cấp đường dẫn đến file torrent (torrent_path) tương ứng với file cần tải
        # ----:         -> Lấy info_hash và pieces từ file torrent (file .json)
        #               -> Gửi yêu cầu lên tracker server kèm theo info_hash + 'event' == 'started'
        #               -> Nhận peers_list từ Tracker server
        #               -> Tạo 1 bảng (pieces_state_table) về tiến trình của tất cả các piece của file cần tải
        #               |    Piece Number   |       State           |
        #               |       Piece 1     |       completed       |
        #               |       Piece 2     |       processing      |
        #               |       Piece 3     |       pending         |
        #               | ..............    |   ................    |
        #               -> pieces_state_table = ['pending'] * pieces (pieces: số lượng piece của file)
        #               -> Cập nhật info_hash + remain_pieces (remain_pieces = [index for index, element in enumerate(pieces_state_table) if element != 'completed'])
        #               -> Lần lượt tạo thread (sender_handle(self, update_pieces_state_table() )) và yêu cầu nhận piece từ các seeder khác (số thread tối đa == len(peers_list)). Và đưa các pieces state về processing
        #               ................... (Còn) ........................
        #               ************* Ngoài lề (không trong method download_handle()) ********************
        #               -> Method sender_handle(self, table) sẽ gọi cập nhật table khi kết thúc việc nhận 1 piece, việc cập nhật sẽ có các bước như sau:
        #                           + Lock nhiều thread truy cập with lock: update; (Tạo 1 lock trước khi tạo thread)
        #                           + Sẽ cập nhật trạng thái của pieces vừa hoàn thành và cấp phát 1 piece mới cho thread hiện tại
        #               ********************************************************************************
        #               -> Liên tục cập nhật mảng remain_pieces
        #               -> Trong hàm download_handle() sẽ liên tục check `remain_pieces` để -> while(remain_pieces is not empty): continue (chờ đến khi các pieces đã trong trạng thái completed);
        #               -> Merge các pieces thành file
        #               -> Gửi event 'completed' đến tracker báo hiệu đã hoàn tất việc download
        ##############################################################################

        # Get metainfo from torrent file
        metainfo_dict = self.get_metainfo(torrent_path)
        # Verify the torrent file
        if self.metainfo_verification(metainfo_dict=metainfo_dict):
            return
        info_hash = metainfo_dict['info_hash']
        pieces_num = metainfo_dict['pieces']
        pieces_path = metainfo_dict['pieces_path']

        # Send a downloading request to the tracker (event == 'started)
        self.send_request_tracker(info_hash=info_hash, peer_id=self.peer_id, event='started', completed_torrent=[])
        response_dict = self.receive_response_tracker()
        # Check the response
        if 'HEADER' not in response_dict:
            print('Error: The response of tracker is invalid (the \'HEADER\' key is not included)')
            return
        if 'status' not in response_dict['HEADER']:
            print('Error: The response of tracker is invalid (the \'status\' key is not included)')
            return
        response_status = response_dict['HEADER']['status']
        if response_status == '404':
            print('Warning: No peer in the swarm has this file. Cancel downloading')
            return
        elif response_status != '200':
            print('Error: The status value is invalid')
            return
        # Check and Get peer_list from response message
        if 'BODY' not in response_dict:
            print('Error: The response of tracker is invalid (the \'BODY\' key is not included)')
            return
        if 'peers' not in response_dict['BODY']:
            print('Error: The response of tracker is invalid (the \'peers\' key is not included)')
            return
        peers_list = self.get_peers_list_msg(response_dict)  # [('127:0:0:1', 5000), ('127:0:0:2', 5001)]

        # Notify to the user about the number of peers
        print(f'Info: There are {len(peers_list)} peers that have this file in the swarm')

        #  Get pieces_num and peers_num and generate lock for multi-threading
        peers_num = len(peers_list)
        lock_update_table = threading.Lock()

        # Create a pieces state table (cấp phát trước các piece và chuyển trạng thái thành processing)
        pieces_state_table = (['processing'] * min(pieces_num, peers_num)) + (['pending'] * max(0, pieces_num - peers_num))

        # Define sender_handle
        def sender_handle(shared_table, info_hash, piece_id, pieces_path, sender_address):
            # ----: Download a piece from sender
            #       Param:  + shared_table: bảng trạng thái các piece (pass by reference, automatically)
            #               + info_hash
            #               + piece_id: số thứ tự của piece
            #               + sender_address: địa chỉ của sender. Vd: ('127:0:0:1', 5000)
            #       0.  Tự cấp phát 1 socket và kết nối đên sender_address
            #       1.  Handshake với sender (hỏi về việc sender có piece đó không)
            #       2.  Mở 1 socket để handshake thông qua việc ping nhau bằng TCP
            #       3.  Mở 1 socket để nhận file qua FTP. Tìm port chưa được dùng để cấp phát (self.find_unused_port()) cho socket hiện tại
            #       5.  Handshake thông qua Peers Protocol (SYNC - SYNC_ACK)
            #           Response to SYNC (SYNC_ACK)
            #       6.  Request 1 piece from seeder
            #       7.  if (Seeder NACK) -> Return
            #           else -> continue
            #       2.  Nhận file thông qua FTP socket
            #       9.  Nhận 1 message thông qua Peers Protocol socket ('type == Completed')
            #       3.  Cập nhật pieces_state_table trong Lock   (in `with lock_update_table:`)
            #       4.  Xin 1 piece_id mới và quay lại bước 1    (in `with lock_update_table:`)
            #       4.1.Nếu không còn piece nào (piece_id == None) -> kết thúc thread này
            ##########################################
            # Create a socket for Peers Protocol
            leecher_socket = socket.socket()
            # Bind the socket to address 
            leecher_socket.bind((self.host, self.find_unused_port()))
            # Establish connection
            leecher_socket.connect(sender_address)

            # Handshake (on Application layer)
            self.send_message_seeder(leecher_socket=leecher_socket, mes_type='SYNC', source_ip=self.host,
                                     source_ftp_port=None, info_hash='', piece_id=None)

            response_seeder = self.receive_message_seeder(socket=leecher_socket)
            # Response checking
            if not self.message_seeder_checking(response_seeder, "HEADER", 'type'):
                return

            if not response_seeder["HEADER"]['type'] == 'SYNC_ACK':
                print('Warning: Can not handshake with a seeder. Close connection with the seeder')
                return

            while True:
                # Create a socket for FTP
                leecher_ftp_socket = FTPReceiver(self.host, self.find_unused_port(), pieces_path)
                leecher_ftp_socket.start()
                # Request a piece
                self.send_message_seeder(leecher_socket=leecher_socket, mes_type='REQ', source_ip=leecher_ftp_socket.host,
                                         source_ftp_port=leecher_ftp_socket.port, info_hash=info_hash, piece_id=piece_id)

                # Receive an ACK of piece
                response_seeder = self.receive_message_seeder(socket=leecher_socket)

                # Response checking
                if not self.message_seeder_checking(response_seeder, "HEADER", 'type'):
                    return
                if response_seeder["HEADER"]['type'] == 'NACK':
                    print('Warning: Can not find out the piece. Close connection with the seeder')
                    return

                # Receive the file (until completed)
                leecher_ftp_socket.receive_file()

                # Receive completed message of seeder
                response_seeder = self.receive_message_seeder(socket=leecher_socket)
                if not self.message_seeder_checking(response_seeder, "HEADER", 'type'):
                    return
                # Response checking
                if not response_seeder["HEADER"]['type'] == 'Completed':
                    print('Warning: Can not download a piece from the seeder. Close connection with the seeder')
                    return

                # Locking access to shared_table (collision -> data hazard)
                with lock_update_table:
                    # ----: update pieces_state_table (shared_table) here
                    #       1. Chuyển trạng thái piece vừa hoàn thành thành 'completed'
                    #       2. Tìm kiếm trong table xem còn piece nào đang trong trạng thái pending không
                    #       3. Nếu còn  then: -> chuyển piece_id = new_piece_id
                    #                         -> chuyển trạng thái piece đó thành 'processing'
                    #                   else: -> gửi 1 'FINISH' message đến seeder
                    shared_table[piece_id] = 'completed'
                    # Nếu: Vẫn còn piece chưa được tiến hành tải
                    if 'pending' in shared_table:
                        piece_id = shared_table.index('pending')
                        shared_table[piece_id] = 'processing'
                    # Nếu: Không còn piece cần tải -> Gửi 1 'FINISH' message đên seeder
                    else:
                        self.send_message_seeder(leecher_socket=leecher_socket, mes_type='FINISH', source_ip=None,
                                                 source_ftp_port=None, info_hash='', piece_id=None)
                        break

        # Create a remain pieces list
        remain_pieces = [index for index, element in enumerate(pieces_state_table) if element != 'completed']

        # Allocate peers to all pieces (pieces_num and peers_num)
        allocating_time = 0
        while (allocating_time <= pieces_num) & (allocating_time <= peers_num):
            sender_address = peers_list[allocating_time]
            sender_handle_thread = threading.Thread(target=sender_handle, args=(pieces_state_table, info_hash, allocating_time, pieces_path, sender_address))
            sender_handle_thread.start()
            allocating_time += 1

        # Update and check pieces_state_table
        while not remain_pieces == []:
            # Notify to user about remain pieces
            print(f'Info: The number of remaining pieces to download: {len(remain_pieces)} piece(s)')
            # Update every 0.5 second
            time.sleep(0.5)

        # Notify to the user: All pieces are downloaded
        print('Info: All pieces are downloaded')

        # Merge file
        print('Info: Reassembling the file')
        reassemble_file(pieces_path, '\\pieces_folder')

        # Notify to the user
        pieces_path_split = pieces_path.split('\\')
        folder_name = pieces_path_split[len(pieces_path_split) - 1]
        file_name = folder_name[:folder_name.rfind('_') - 1] + '.' + folder_name[folder_name.rfind('_') + 1:]
        print(f'Info: The file has been added to the pieces_folder\\{file_name} directory')

        # Send 'completed' message to the tracker
        self.send_request_tracker(info_hash=info_hash, peer_id=self.peer_id, event='completed', completed_torrent=[])

    def handle_user_command(self, user_command):
        # Parse the user command
        if ':' not in user_command:
            print('Error: The command is invalid (\':\')')
            return
        command_split = user_command.split(':')
        if not len(command_split) == 2:
            print('Error: The command is invalid (\'wrong format\')')
            return
        command_type = command_split[0]
        command_param = command_split[1]
        if command_type == 'Download':
            print('Info: Handling the downloading command')
            self.download_handle(command_param)
        elif command_type == 'Upload':
            print('Info: Handling the uploading command')
            self.upload_handle(command_param)
        else:
            print("Error: Wrong command format (command type)")
        # if type of the command is Uploading
        #       upload_handle():
        #       -> Copy file vào pieces_folder
        #       -> Chia file vào folder phù hợp (vd: myCV.pdf -> đưa vào folder myCV_pdf trong folder pieces_folder)
        # if type of the command is Downloading
        #       download_handle():
        #       -> Chia file

        return
    ########################## Handling method (end) ##########################################

    ######################## Protocol method (start) ######################################
    def connect_to_tracker(self, tracker_address):
        # Connect to the tracker server
        self.client_socket.connect(tracker_address)

    def seeder_init(self):
        # Allocate a unused port
        leecher_handle_thread_port = self.find_unused_port()
        self.seeder_port = leecher_handle_thread_port
        # Create a socket
        self.seeder_socket = socket.socket()
        self.seeder_socket.bind((self.seeder_host, leecher_handle_thread_port))

    def send_request_tracker(self, info_hash, peer_id, event, completed_torrent):
        # Wait until sender is released
        while self.tracker_request_lock == 1:
            continue

        # Lock sending message
        self.tracker_request_lock = 0

        # Generate request
        request = {
            'TOPIC': 'TORRENT',
            'HEADER': {
                'event': event,
                'source_host': self.host,
                'source_port': self.port,
                'seeder_host': self.seeder_host,
                'seeder_port': self.seeder_port
            },
            'BODY': {
                'peer_id': peer_id,
                'info_hash': info_hash,
                'completed_list': completed_torrent
            }
        }

        # Pre encode request
        request = self.pre_encode_convert(request)
        # Send a request to the tracker
        request_encoded = bencodepy.encode(request)
        self.client_socket.send(request_encoded)

        # Unlock sending message to tracker
        self.tracker_request_lock = 1

    def receive_response_tracker(self):
        # Description: Just receive response (not include 'keep-alive' message)
        return self.tracker_response_queue.get()

    def receive_message_tracker(self):
        # Receive the response from the tracker
        response = self.client_socket.recv(1024)
        # response_dict = bencodepy.decode(response)
        response_dict = bencodepy.decode(response)
        # Post decode message
        response_dict = self.post_decode_convert(response_dict)
        return response_dict

    def send_message_seeder(self, leecher_socket, mes_type, source_ip, source_ftp_port, info_hash, piece_id):
        message_seeder = {
            "TOPIC": "DOWNLOADING",
            "HEADER": {
                'type': mes_type,
                'source_ip': source_ip,
                'source_ftp_port': source_ftp_port,
                'info_hash': info_hash,
                'piece_id': piece_id
            }
        }
        leecher_socket.send(message_seeder)

    def receive_message_seeder(self, socket):
        message = socket.recv(1024)
        return message

    def receive_message(self, conn):
        data = conn.recv(1024)
        message = json.loads(data.decode())
        return message

    def send_message(self, conn, message):
        data = json.dumps(message).encode()  # dump dict to str, then encode str to bytes
        conn.sendall(data)

    def handle_response_tracker(self, response_dict):
        # Parse the response
        if 'HEADER' not in response_dict:
            print('Info: The init message of the tracker is invalid (the \'HEADER\' key is not included)')
            return 0
        if 'status' not in response_dict['HEADER']:
            print('Info: The init message of the tracker is invalid (the \'status\' key is not included)')
            return 0
        if 'event' not in response_dict['HEADER']:
            print('Info: The init message of the tracker is invalid (the \'event\' key is not included)')
            return 0
        status_field = response_dict['HEADER']['status']
        if status_field == '404':  # Wrong information of metainfo file
            print('Info: ', response_dict['message'])
            return 0
        elif status_field == '100':  # Wrong username or password
            print("Info: Connected")
            return 1

    def handle_keep_alive_tracker(self):
        self.send_request_tracker(info_hash='', peer_id=self.peer_id, event='check_response', completed_torrent=self.completed_list)
    ######################## Protocol method (end) ######################################

    ######################## Thread method (start) ######################################
    # Description: Maintain connection with the tracker
    # def maintain_connection(self):
    #
    #     # Close: Máy bạn duy trì kết nối với tracker -> Cập nhật completed_list thường xuyên (vì người dùng có thể đưa thêm 1 file torrent mới lên hệ thống)
    #     # Description:  - Interval = 1 second
    #     #               - Message = {'event': 'check_response'}
    #
    #     return
    #
    # def user_download_check(self):
    #     # Close: Người dùng muốn tải một file trong các file torrent mà tracker đã cập nhật (nhớ kiểm tra xem file đó có trong self.file_list chưa)
    #     return
    # def user_upload_check(self):
    #     # -> Người dùng tạo 1 file torrent - "\TorrentList\abc.txt"
    #     # -> Tách nó ra 1 folder gồm casc piece (giả sử dc 100 mảnh)
    #     #       folder name:    abc_txt             <file_name>_<type>
    #     #       piece name:     abc_txt_0.bin       <folder_name>_<piece_num>.bin
    #     #                       abc_txt_1.bin
    #     #                       abc_txt_2.bin
    #     # -> Đưa vô completed_list
    #     # Close: Người dùng tạo mới 1 file torrent từ 1 file sẵn có trong máy, sau đó cập nhật file torrent đó vào Metainfo file và self.file_list (Việc cập nhật lên server sẽ ằm ở thread maintain_connection)
    #     return

    def tracker_check(self):
        while True:
            message = self.receive_message_tracker()
            # Handle immediately (if message is a keep-alive message)
            if 'HEADER' in message:
                if 'status' in message['HEADER']:
                    if message['status'] == '505':
                        self.handle_keep_alive_tracker()
                        return
            self.tracker_response_queue.put(message)

    def user_check(self):
        while True:
            time.sleep(0.2)
            user_command = input("User command-line: ")
            self.user_command_queue.put(user_command)

    def user_handle(self):
        while True:
            if self.user_command_queue.qsize() > 0:
                self.handle_user_command(self.user_command_queue.get())

    def leecher_handle(self, receiver_socket, listen_port):
        def send_message_leecher(receiver_socket_in, msg_type, source_ip_in=self.host, source_port_in=listen_port, info_hash_in='', piece_id_in=None):
            packet_in = {
                "TOPIC": "UPLOADING",
                "HEADER": {
                    'type': msg_type,
                    'source_ip': source_ip_in,
                    'source_port': source_port_in,
                    'info_hash': info_hash_in,
                    'piece_id': piece_id_in
                }
            }
            self.send_message(receiver_socket_in, packet_in)

        # Handshake (receiver -> sender)
        packet = self.receive_message(receiver_socket)  # Get packet from receiver

        if not self.message_seeder_checking(packet, 'HEADER', 'type'):
            print('Info: the response of a seeder is invalid (-1)')
            return

        if packet['HEADER']['type'] == "SYNC":  # If SYNC, then SYNC accept
            send_message_leecher(receiver_socket, msg_type='SYNC_ACK', source_ip_in=self.host, source_port_in=listen_port)
            # self.send_message(receiver_socket, packet)

        while True:
            # Receive REQ/FINISH message
            packet = self.receive_message(receiver_socket)
            # Checking
            if not self.message_seeder_checking(packet, 'HEADER', 'type'):
                print('Error: the response of a seeder is invalid (-2)')
                return
            # Get message type
            message_type = packet['HEADER']['type']
            if message_type == 'FINISH':
                return
            elif not message_type == 'REQ':
                print('Error: the response of a seeder is invalid (-5)')
                return

            # This is a request message
            if not self.message_seeder_checking(packet, 'HEADER', 'source_ip'):
                print('Error: the response of a seeder is invalid')
                return
            if not self.message_seeder_checking(packet, 'HEADER', 'source_ftp_port'):
                print('Error: the response of a seeder is invalid')
                return
            dest_host_in = packet['HEADER']['source_ip']
            dest_port_in = packet['HEADER']['source_ftp_port']

            # Handshake (sender -> receiver)
            # Nếu sender có file đó (check 'info_hash' xem có ko)
            # input_info_hash = None
            if not self.message_seeder_checking(packet, 'HEADER', 'info_hash'):
                print('Error: the response of a seeder is invalid (666)')  # 666
                return

            if not self.message_seeder_checking(packet, 'HEADER', 'piece_id'):
                print('Error: the response of a seeder is invalid (777)')  # 777
                return
            piece_id = packet['HEADER']['pieace_id']
            piece_path = self.search_completed_list(packet['HEADER']['info_hash'])
            send_successed = False
            if piece_path:
                print('Info: Sending a piece')
                send_message_leecher(receiver_socket_in=receiver_socket, msg_type='ACK', source_ip_in=self.host,
                                     source_port_in=listen_port, info_hash_in=packet['HEADER']['info_hash'],
                                     piece_id_in=piece_id)

                # If the file exist, send the file

                needing_file = self.search_chunk_file(piece_path, piece_id)

                send_successed = send_file(self.host, self.find_unused_port(), dest_host_in, dest_port_in, needing_file)

                # Send notify after successfully sending file is include in the send_file func
            else:
                # Nếu sender ko có file đó
                send_message_leecher(receiver_socket_in=receiver_socket, msg_type='NACK', source_ip_in=self.host,
                                     source_port_in=listen_port, info_hash_in=packet['HEADER']['info_hash'],
                                     piece_id_in=piece_id)

            if send_successed:
                send_message_leecher(receiver_socket_in=receiver_socket, msg_type='Completed', source_ip_in=self.host,
                                     source_port_in=listen_port, info_hash_in=packet['HEADER']['info_hash'],
                                     piece_id_in=piece_id)
                # Send this packet to Receiver
                # Continue

    def leecher_check(self):
        self.seeder_socket.listen(5)
        while True:
            # Tạo 1 thread khi có 1 leecher kết nối đến và thread đó handle phần giao tiếp
            receiver_socket, address = self.seeder_socket.accept()
            listen_port = self.find_unused_port()
            thread = threading.Thread(target=self.leecher_handle, args=(receiver_socket, listen_port))
            thread.start()
            break
    ######################### Thread method (end) #######################################

    ######################### Flow method (start) #######################################
    def establish_connection(self):
        info_hash = ''
        print("Info: Connecting to the tracker ......")
        while True:
            self.send_request_tracker(info_hash, self.peer_id, 'init', self.completed_list)
            response = self.receive_message_tracker()
            if self.handle_response_tracker(response) == 1:
                break

    def start(self):
        # Load the previous param of the peer
        self.load_param("TorrentList.json")

        # User login
        self.user_login()

        # Create a socket
        self.client_socket = socket.socket()

        # Bind the socket to address and port
        self.client_socket.bind((self.host, self.port))

        # Create a seeder socket
        self.seeder_init()

        # Establish connection (Transport layer handshake)
        self.connect_to_tracker(self.tracker_address)

        # Establish connection (Application layer Handshake): The peer send metainfo to the tracker
        self.establish_connection()

        # Create 3 main threads -> leecher_check (another peer want to download your file)
        #                       -> tracker_check: receive message from the tracker and store the message to queue
        #                       -> user_check: receive user's command and store to a queue
        #                       -> user_handle: Handle the command of user
        #                       (delete) -> maintain_connection (keep-alive and updating metainfo message with the tracker)
        #                       (delete) -> user_download_check: user want to download a new file  -> "start downloading" stage
        #                       (delete) -> user_upload_check: user want to upload a new torrent file to tracker
        leecher_check_thread = threading.Thread(target=self.leecher_check)
        leecher_check_thread.start()

        tracker_check_thread = threading.Thread(target=self.tracker_check)
        tracker_check_thread.start()

        user_check_thread = threading.Thread(target=self.user_check)
        user_check_thread.start()

        user_handle_thread = threading.Thread(target=self.user_handle)
        user_handle_thread.start()
    ######################### Flow method (end) #######################################



def find_unused_port(start_port=5003, end_port=65535):
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('localhost', port))
            except OSError:
                # Port is already in use
                continue
            return port
    raise Exception("Error: No unused port found in the specified range (You are using too many resources)")


if __name__ == '__main__':
    peer = Peer('localhost', find_unused_port())
    peer.start()