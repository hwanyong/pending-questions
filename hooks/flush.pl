# 인자로 받은 파일과 그 폴더의 내용을 디스크까지 기록한다. $.fs.write 에는 이 수단이 없다.
# 입력: 파일 경로 1개. 출력: 성공이면 종료 코드 0, 실패하면 stderr 에 이유를 적고 0 이 아닌 코드.
use strict;
use warnings;
use File::Basename qw(dirname);
use IO::Handle;

# macOS 의 fsync 는 드라이브 캐시를 비우지 않는다. 51 은 sys/fcntl.h 의 F_FULLFSYNC 이고
# perl 의 Fcntl 모듈에는 이 이름이 없다.
use constant F_FULLFSYNC => 51;

my $flush = sub {
    my ($path) = @_;
    open(my $handle, '<', $path) or die "open $path: $!\n";
    return if $^O eq 'darwin' && fcntl($handle, F_FULLFSYNC, 0);
    # F_FULLFSYNC 를 받지 않는 파일 시스템(SMB 등)과 macOS 가 아닌 OS 는 fsync 로 기록한다.
    $handle->sync or die "fsync $path: $!\n";
};

my $path = shift // die "usage: flush.pl <file>\n";
$flush->($path);
$flush->(dirname($path));
